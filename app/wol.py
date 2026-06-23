from flask import Flask, request, render_template, redirect, url_for, jsonify, flash, session
import hmac
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
import logging
import socket
import sqlite3
import struct
import subprocess
import os
import time
import ipaddress
import re
import fcntl
import tempfile
import contextlib
from urllib.parse import urlparse
from markupsafe import Markup

log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
  level=getattr(logging, log_level, logging.INFO),
  format='[%(asctime)s] [%(levelname)s] %(message)s',
  datefmt='%Y-%m-%d %H:%M:%S %z'
)
logger = logging.getLogger(__name__)

ping_timeout = os.environ.get('PING_TIMEOUT', 300)
arp_timeout = os.environ.get('ARP_TIMEOUT', 300)
tcp_timeout = os.environ.get('TCP_TIMEOUT', 1)
arp_interface = os.environ.get('ARP_INTERFACE')
l2_wol_packet = os.environ.get('ENABLE_L2_WOL_PACKET', 'false').lower() == 'true'
l2_interface = os.environ.get('L2_INTERFACE', 'eth0')
cron_filename = '/etc/cron.d/gptwol'
computer_filename = 'db/computers.txt'
cron_lock_filename = '/tmp/gptwol-cron.lock'


@contextlib.contextmanager
def cron_lock():
  # Serialize all cron read-modify-write operations across gunicorn workers.
  lf = open(cron_lock_filename, 'w')
  try:
    fcntl.flock(lf, fcntl.LOCK_EX)
    yield
  finally:
    fcntl.flock(lf, fcntl.LOCK_UN)
    lf.close()


def atomic_write_lines(path, lines):
  # Write lines to path atomically (temp file in same dir + os.replace).
  d = os.path.dirname(path) or '.'
  fd, tmp = tempfile.mkstemp(dir=d)
  try:
    with os.fdopen(fd, 'w') as f:
      f.writelines(lines)
    os.replace(tmp, path)
  except Exception:
    try:
      os.unlink(tmp)
    except OSError:
      pass
    raise


def sanitize_link(raw):
  # Accept only http(s) links; block javascript:/data:/file:/mailto: etc.
  raw = (raw or '').strip()
  if not raw:
    return None
  try:
    parsed = urlparse(raw)
  except ValueError:
    return None
  if parsed.scheme:
    # Explicit scheme present -> must be http/https with a host
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
      return None
    return raw
  # No scheme -> assume http:// in front of a bare host
  candidate = 'http://' + raw
  if not urlparse(candidate).netloc:
    return None
  return candidate

app = Flask(__name__, static_folder='templates')

def _wf_secret_key():
  k = os.environ.get('SECRET_KEY')
  if k:
    return k
  path = '/app/db/.secret_key'
  try:
    os.makedirs('/app/db', exist_ok=True)
    # Serialize across gunicorn workers so a fresh DB doesn't race into divergent keys
    lock = open('/app/db/.secret_key.lock', 'w')
    try:
      fcntl.flock(lock, fcntl.LOCK_EX)
      if os.path.exists(path):
        existing = open(path).read().strip()
        if existing:
          return existing
      k = os.urandom(32).hex()
      with open(path, 'w') as f:
        f.write(k)
      os.chmod(path, 0o600)
      logger.info("Generated persistent SECRET_KEY at %s", path)
      return k
    finally:
      fcntl.flock(lock, fcntl.LOCK_UN)
      lock.close()
  except Exception as e:
    logger.warning("Could not persist SECRET_KEY (%s); using ephemeral key", e)
    return os.urandom(32).hex()
app.secret_key = _wf_secret_key()

# --- Simple optional login (WOL-F) ---
ENABLE_LOGIN = os.environ.get('ENABLE_LOGIN', 'false').strip().lower() == 'true'
LOGIN_USERNAME = os.environ.get('USERNAME', 'admin')
LOGIN_PASSWORD = os.environ.get('PASSWORD', '')
# Fail closed: refuse to start with a default/empty password when login is enabled
if ENABLE_LOGIN and not LOGIN_PASSWORD:
  raise RuntimeError(
    "ENABLE_LOGIN=true requires a non-empty PASSWORD environment variable "
    "(refusing to start with a default/empty password)."
  )
# Basic in-memory login rate limiting (per source IP)
LOGIN_MAX_ATTEMPTS = int(os.environ.get('LOGIN_MAX_ATTEMPTS', '8'))
LOGIN_WINDOW = int(os.environ.get('LOGIN_WINDOW', '300'))
_RL_DB = '/app/db/ratelimit.db'
def _rl_conn():
  con = sqlite3.connect(_RL_DB, timeout=5)
  con.execute('CREATE TABLE IF NOT EXISTS login_attempts (ip TEXT PRIMARY KEY, count INTEGER NOT NULL, first_ts REAL NOT NULL)')
  return con
def _rl_is_limited(ip, now):
  try:
    con = _rl_conn()
    try:
      row = con.execute('SELECT count, first_ts FROM login_attempts WHERE ip=?', (ip,)).fetchone()
    finally:
      con.close()
    if not row:
      return False
    cnt, first = row
    if now - first > LOGIN_WINDOW:
      return False
    return cnt >= LOGIN_MAX_ATTEMPTS
  except Exception as e:
    logger.warning("rate-limit check failed (%s); allowing", e)
    return False
def _rl_record_fail(ip, now):
  try:
    con = _rl_conn()
    try:
      row = con.execute('SELECT count, first_ts FROM login_attempts WHERE ip=?', (ip,)).fetchone()
      cnt, first = row if row else (0, now)
      if now - first > LOGIN_WINDOW:
        cnt, first = 0, now
      con.execute('INSERT INTO login_attempts(ip, count, first_ts) VALUES(?,?,?) ON CONFLICT(ip) DO UPDATE SET count=excluded.count, first_ts=excluded.first_ts', (ip, cnt + 1, first))
      con.commit()
    finally:
      con.close()
  except Exception as e:
    logger.warning("rate-limit record failed (%s)", e)
def _rl_clear(ip):
  try:
    con = _rl_conn()
    try:
      con.execute('DELETE FROM login_attempts WHERE ip=?', (ip,))
      con.commit()
    finally:
      con.close()
  except Exception as e:
    logger.warning("rate-limit clear failed (%s)", e)
WF_LANGUAGE = (os.environ.get('LANGUAGE', 'de') or 'de').strip().lower()
if WF_LANGUAGE not in ('de', 'en'): WF_LANGUAGE = 'de'
# Feature-Flags explizit ans Template (statt das ganze os-Modul -> kein env-Leak in Jinja-Scope)
WF_ENABLE_REFRESH = os.environ.get('ENABLE_REFRESH') != 'false'
WF_REFRESH_INTERVAL_MS = max(int(os.environ.get('REFRESH_INTERVAL', '30') or 30), 5) * 1000
WF_ENABLE_ADD_DEL = os.environ.get('ENABLE_ADD_DEL') != 'false'

db_path = '/app/db/computers.db'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
# When the app serves HTTPS itself (ENABLE_HTTPS), mark the session cookie Secure automatically
_wf_https = os.environ.get('ENABLE_HTTPS', 'false').strip().lower() == 'true'
app.config['SESSION_COOKIE_SECURE'] = _wf_https or (os.environ.get('SESSION_COOKIE_SECURE', 'false').strip().lower() == 'true')
# Browsers scope cookies by HOST, not port -> two WOL-F instances on the same host
# (e.g. :2600 and :2601) would otherwise share/overwrite the same 'session' cookie and
# break each other's CSRF/session. Namespace the cookie per instance (by PORT, overridable).
_wf_port = (os.environ.get('PORT', '') or '').strip()
app.config['SESSION_COOKIE_NAME'] = os.environ.get('SESSION_COOKIE_NAME') or (('wolf_session_' + _wf_port) if _wf_port else 'wolf_session')
# Fail closed: HTTPS ohne Login wuerde ungeschuetzte Geraetesteuerung exponieren -> Start verweigern
if _wf_https and not ENABLE_LOGIN:
  raise RuntimeError(
    "ENABLE_HTTPS=true requires ENABLE_LOGIN=true (refusing to serve WOL-F over HTTPS without authentication)."
  )
db = SQLAlchemy(app)
# Token ist die CSRF-Abwehr; Referer/Host-Kopplung lockern -> funktioniert hinter Reverse-Proxy
app.config['WTF_CSRF_SSL_STRICT'] = False
csrf = CSRFProtect(app)


@app.after_request
def wf_security_headers(resp):
  resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
  resp.headers.setdefault('X-Frame-Options', 'DENY')
  resp.headers.setdefault('Referrer-Policy', 'no-referrer')
  return resp


@app.before_request
def require_login():
  if not ENABLE_LOGIN:
    return
  if request.endpoint in ('static', 'login'):
    return
  if session.get('logged_in'):
    return
  if request.method == 'GET':
    return redirect(url_for('login'))
  return ('Login required.', 401)


@app.route('/login', methods=['GET', 'POST'])
def login():
  if not ENABLE_LOGIN or session.get('logged_in'):
    return redirect(url_for('wol_form'))
  error = False
  if request.method == 'POST':
    ip = request.remote_addr or 'unknown'
    now = time.time()
    if _rl_is_limited(ip, now):
      logger.warning("Login rate-limited for %s", ip)
      return ('Too many login attempts. Try again later.', 429)
    u = request.form.get('username', '')
    p = request.form.get('password', '')
    if hmac.compare_digest(u.encode('utf-8'), LOGIN_USERNAME.encode('utf-8')) and hmac.compare_digest(p.encode('utf-8'), LOGIN_PASSWORD.encode('utf-8')):
      _rl_clear(ip)
      session['logged_in'] = True
      session.permanent = True
      return redirect(url_for('wol_form'))
    _rl_record_fail(ip, now)
    logger.warning("Failed login attempt from %s", ip)
    error = True
  return render_template('login.html', error=error, lang=WF_LANGUAGE)


@app.route('/logout')
def logout():
  session.clear()
  return redirect(url_for('login'))

def generate_modal_html(messages, title):
  return render_template('generate_modal.html', title=title, messages=messages)

class Computer(db.Model):
  name = db.Column(db.String(64), nullable=False)
  mac_address = db.Column(db.String(17), unique=True, primary_key=True, nullable=False)
  ip_address = db.Column(db.String(45), nullable=False)
  test_type = db.Column(db.String(10), nullable=False)
  type = db.Column(db.String(16))
  link = db.Column(db.String(255))

def migrate_txt_to_db():
  if not os.path.exists(computer_filename):
    return

  with open(computer_filename) as f:
    for line in f:
      fields = line.strip().split(',')
      if len(fields) < 3:
        continue
      name, mac, ip = fields[0], fields[1], fields[2]
      test_type = fields[3] if len(fields) > 3 else 'icmp'

      if not Computer.query.filter_by(mac_address=mac).first():
        c = Computer(name=name, mac_address=mac, ip_address=ip, test_type=test_type)
        db.session.add(c)

  db.session.commit()
  os.rename(computer_filename, f"{computer_filename}.old")

def load_computers():
  computers = []

  for c in Computer.query.all():
    computers.append({
      'name': c.name,
      'mac_address': c.mac_address,
      'ip_address': c.ip_address,
      'test_type': c.test_type,
      'type': c.type,
      'link': c.link
    })

  # Cron loading
  if not os.path.exists(cron_filename):
    open(cron_filename, 'w').close()

  with open(cron_filename) as f:
    for line in f:
      raw = line.strip()
      paused = False
      if raw.startswith('#PAUSED '):
        paused = True
        raw = raw[len('#PAUSED '):].strip()
      if not raw or raw.startswith('#'):
        continue
      fields = raw.split()
      if len(fields) < 7:
        continue
      schedule = ' '.join(fields[:5])
      mac_address = fields[-1]
      reversed_mac_address = ':'.join(reversed(mac_address.split(':')))
      for computer in computers:
        if computer['mac_address'] == mac_address:
          computer['cron_wol_schedule'] = schedule
          if paused:
            computer['cron_paused'] = True
        if computer['mac_address'] == reversed_mac_address:
          computer['cron_sol_schedule'] = schedule
          if paused:
            computer['cron_paused'] = True

  return computers

def get_interface_mac(interface):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        info = fcntl.ioctl(
            s.fileno(),
            0x8927,  # SIOCGIFHWADDR
            struct.pack('256s', interface.encode('utf-8')[:15])
        )
        return info[18:24]  # MAC address bytes
    finally:
        s.close()

def send_l2_wol_packet(mac_address, interface):
    # Clean and convert target MAC address to bytes
    mac_clean = mac_address.replace(':', '').replace('-', '')
    mac_bytes = bytes.fromhex(mac_clean)

    # Build the magic packet
    magic_packet = b'\xff' * 6 + mac_bytes * 16

    # Destination: broadcast, Source: real MAC from interface
    dst_mac = b'\xff\xff\xff\xff\xff\xff'
    src_mac = get_interface_mac(interface)
    eth_type = b'\x08\x42'  # Wake-on-LAN EtherType

    # Construct Ethernet frame
    ether_frame = dst_mac + src_mac + eth_type + magic_packet

    # Send via raw socket
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
    try:
        s.bind((interface, 0))
        s.send(ether_frame)
    finally:
        s.close()

def send_wol_packet(mac_address):
  # Convert the MAC address to a packed binary string
  packed_mac = struct.pack('!6B', *[int(x, 16) for x in mac_address.split(':')])

  # Create a socket and send the WOL packet
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
  s.sendto(b'\xff' * 6 + packed_mac * 16, ('<broadcast>', 9))

def is_computer_awake(ip_address, port):
  if not port or port.lower() == 'icmp':
    return is_computer_awake_icmp(ip_address)
  if port.lower() == 'arp':
    return is_computer_awake_arp(ip_address)
  else:
    port_int = int(port)
    return is_computer_awake_tcp(ip_address, port_int)

def is_computer_awake_icmp(ip_address, timeout=ping_timeout):
  # Use the fping command with a timeout to check if the computer is awake
  result = subprocess.run(['fping', '-t', str(timeout), '-c', '1', ip_address], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
  return result.returncode == 0

def is_computer_awake_arp(ip_address, timeout=arp_timeout):
  # Use the arp-scan command to check if the computer is awake
  command = ['arp-scan', '-qx', '-t', str(timeout), ip_address]
  if arp_interface:
    command += ['-I', arp_interface]

  result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
  # Check if there is any output in stdout
  return bool(result.stdout.strip())

def is_computer_awake_tcp(ip_address, port, timeout=tcp_timeout):
  # Use nc (netcat) to check if the TCP port is open
  result = subprocess.run(['nc', '-z', '-w', str(timeout), ip_address, str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
  return result.returncode == 0

def check_mac_exist(mac_address):
  return db.session.query(Computer.mac_address).filter_by(mac_address=mac_address).first() is not None

def check_invalid_name(name):
  return ',' in name

def check_invalid_ip(ip):
  try:
    ipaddress.ip_address(ip)
    return False # Valid IP
  except ValueError:
    return True # Invalid IP

def check_invalid_mac(mac):
  # Regular expression for validating a MAC address
  mac_pattern = r'([0-9a-fA-F]{2}:){5}([0-9a-fA-F]{2})'
  # fullmatch rejects trailing newlines / extra chars (prevents cron-line injection)
  if re.fullmatch(mac_pattern, mac):
    return False  # Valid MAC address
  else:
    return True   # Invalid Mac address

def check_invalid_test_type(test_type):
  # Check if test_type is "icmp"/"arp" or a valid TCP port number (1-65535)
  if test_type == "icmp" or test_type == "arp":
    return False  # "icmp" is valid
  return not (test_type.isdigit() and 1 <= int(test_type) <= 65535)

def check_invalid_cron(cron):
  # Regular expressions for each field
  patterns = [
    r'^(\*|[1-5]?[0-9](-[1-5]?[0-9])?)(\/[1-9][0-9]*)?(,(\*|[1-5]?[0-9](-[1-5]?[0-9])?)(\/[1-9][0-9]*)?)*$',
    r'^(\*|(1?[0-9]|2[0-3])(-(1?[0-9]|2[0-3]))?)(\/[1-9][0-9]*)?(,(\*|(1?[0-9]|2[0-3])(-(1?[0-9]|2[0-3]))?)(\/[1-9][0-9]*)?)*$',
    r'^(\*|([1-9]|[1-2][0-9]?|3[0-1])(-([1-9]|[1-2][0-9]?|3[0-1]))?)(\/[1-9][0-9]*)?(,(\*|([1-9]|[1-2][0-9]?|3[0-1])(-([1-9]|[1-2][0-9]?|3[0-1]))?)(\/[1-9][0-9]*)?)*$',
    r'^(\*|([1-9]|1[0-2]?)(-([1-9]|1[0-2]?))?)(\/[1-9][0-9]*)?(,(\*|([1-9]|1[0-2]?)(-([1-9]|1[0-2]?))?)(\/[1-9][0-9]*)?)*$',
    r'^(\*|[0-6](-[0-6])?)(\/[1-9][0-9]*)?(,(\*|[0-6](-[0-6])?)(\/[1-9][0-9]*)?)*$'
  ]

  # Split the cron expression into its components
  parts = cron.split()
  if len(parts) != 5:
    return True  # Invalid if not exactly 5 parts

  # Validate each part using the corresponding regex
  return any(not re.match(pattern, part) for pattern, part in zip(patterns, parts))

def delete_cron_entry(request_mac_address):
  # Exact MAC match only: WOL stores under mac, SOL under reversed-mac. Matching
  # both here would let delete_wol_cron also nuke the SOL entry (and vice versa).
  # delete_computer() cleans both directions via two explicit calls.
  with cron_lock():
    with open(cron_filename, 'r') as f:
      lines = f.readlines()

    # Remove every cron line for this MAC, including paused (#PAUSED ) ones.
    # Genuine comments and blank lines are preserved.
    new_lines = []
    deleted = False
    for line in lines:
      raw = line.rstrip('\n')
      is_paused = raw.startswith('#PAUSED ')
      work = raw[len('#PAUSED '):] if is_paused else raw
      stripped = work.strip()
      if not stripped or (stripped.startswith('#') and not is_paused):
        new_lines.append(line)
        continue
      fields = stripped.split()
      if len(fields) >= 7 and fields[-1] == request_mac_address:
        deleted = True
        continue
      new_lines.append(line)

    if deleted:
      atomic_write_lines(cron_filename, new_lines)
  return redirect(url_for('wol_form'))

@app.route('/')
def wol_form():
  computers = load_computers()
  return render_template('wol_form.html', computers=computers, is_computer_awake=lambda *_: "asleep", enable_login=ENABLE_LOGIN, lang=WF_LANGUAGE, enable_refresh=WF_ENABLE_REFRESH, refresh_interval_ms=WF_REFRESH_INTERVAL_MS, enable_add_del=WF_ENABLE_ADD_DEL)

@app.route('/delete_computer', methods=['POST'])
def delete_computer():
  mac_address = request.form['mac_address']

  # Delete the wol cron schedule for the mac_address
  delete_cron_entry(mac_address)
  # Delete the sol cron schedule for the reversed_mac_address
  reversed_mac_address = ':'.join(reversed(mac_address.split(':')))
  delete_cron_entry(reversed_mac_address)

  Computer.query.filter_by(mac_address=mac_address).delete()
  db.session.commit()

  return redirect(url_for('wol_form'))

@app.route('/add_computer', methods=['POST'])
def add_computer():
  name = request.form['name']
  mac_address = request.form['mac_address']
  ip_address = request.form['ip_address']
  test_type = request.form['test_type']
  dev_type = (request.form.get('type') or '').strip() or None
  dev_link = sanitize_link(request.form.get('link'))

  messages = []
  # Check Entries
  if check_mac_exist(mac_address):
    messages.append(f'Device with MAC {mac_address} already exists.')
  if check_invalid_name(name):
    messages.append(f'NAME: {name} is invalid. Character , is invalid')
  if check_invalid_ip(ip_address):
    messages.append(f'IP: {ip_address} is invalid.')
  if check_invalid_mac(mac_address):
    messages.append(f'MAC: {mac_address} is invalid.')
  if check_invalid_test_type(test_type):
    messages.append(f'Status check: {test_type} is invalid. Enter "icmp", "arp" or a valid TCP port number.')
  if messages:
    return generate_modal_html(messages, 'Add Device Error')

  new_computer = Computer(name=name, mac_address=mac_address, ip_address=ip_address, test_type=test_type, type=dev_type, link=dev_link)
  db.session.add(new_computer)
  db.session.commit()

  return redirect(url_for('wol_form'))

@app.route('/edit_computer', methods=['POST'])
def edit_computer():
  name = request.form['name']
  mac_address = request.form['mac_address']
  ip_address = request.form['ip_address']
  test_type = request.form['test_type']
  dev_type = (request.form.get('type') or '').strip() or None
  dev_link = sanitize_link(request.form.get('link'))

  # Find the computer being edited
  computer_to_edit = Computer.query.filter_by(mac_address=mac_address).first()

  messages = []
  if computer_to_edit is None:
    messages.append(f'Device with MAC address: {mac_address} not found.')
  if check_invalid_name(name):
    messages.append(f'NAME: {name} is invalid. Character , is invalid')
  if check_invalid_ip(ip_address):
    messages.append(f'IP: {ip_address} is invalid.')
  if check_invalid_test_type(test_type):
    messages.append(f'Status check: {test_type} is invalid. Enter "icmp", "arp" or a valid TCP port number.')
  if messages:
    return generate_modal_html(messages, 'Edit Device Error')

  if (computer_to_edit.name == name and computer_to_edit.ip_address == ip_address and computer_to_edit.test_type == test_type and computer_to_edit.type == dev_type and computer_to_edit.link == dev_link):
    messages.append(f'No change was made.')
    return generate_modal_html(messages, 'Edit Device Info')

  computer_to_edit.name = name
  computer_to_edit.ip_address = ip_address
  computer_to_edit.test_type = test_type
  computer_to_edit.type = dev_type
  computer_to_edit.link = dev_link
  db.session.commit()

  return redirect(url_for('wol_form'))

def add_cron(mac_address, request_cron):
  messages = []
  # Validate MAC before writing to /etc/cron.d (prevents root command injection via crafted MAC)
  if check_invalid_mac(mac_address):
    messages.append('Invalid MAC address!')
    return generate_modal_html(messages, 'Add Cron Error')
  # Check Entries
  if check_invalid_cron(request_cron):
    messages.append('Invalid cron expression!')
    messages.append(Markup('See : <a href="https://crontab.guru/" target="_blank" rel="noopener noreferrer">Crontab maker</a>'))
    return generate_modal_html(messages, 'Add Cron Error')

  cron_command = f"{request_cron} root /usr/local/bin/wakeonlan {mac_address}"
  with cron_lock():
    with open(cron_filename, "a") as f:
      f.write(f"{cron_command}\n")
  return redirect(url_for('wol_form'))

@app.route('/add_wol_cron', methods=['POST'])
def add_wol_cron():
  request_mac_address = request.form['mac_address']
  request_cron = request.form['cron_request']
  return add_cron(request_mac_address, request_cron)

@app.route('/add_sol_cron', methods=['POST'])
def add_sol_cron():
  request_mac_address = request.form['mac_address']
  reversed_mac_address = ':'.join(reversed(request_mac_address.split(':')))
  request_cron = request.form['cron_request']
  return add_cron(reversed_mac_address, request_cron)

@app.route('/delete_wol_cron', methods=['POST'])
def delete_wol_cron():
  request_mac_address = request.form['mac_address']
  delete_cron_entry(request_mac_address)
  return redirect(url_for('wol_form'))

@app.route('/delete_sol_cron', methods=['POST'])
def delete_sol_cron():
  request_mac_address = request.form['mac_address']
  reversed_mac_address = ':'.join(reversed(request_mac_address.split(':')))
  delete_cron_entry(reversed_mac_address)
  return redirect(url_for('wol_form'))

@app.route('/toggle_cron', methods=['POST'])
def toggle_cron():
  request_mac = request.form['mac_address']
  reversed_mac = ':'.join(reversed(request_mac.split(':')))
  with cron_lock():
    with open(cron_filename, 'r') as f:
      lines = f.readlines()
    new_lines = []
    result_paused = False
    matched = False
    for line in lines:
      raw = line.rstrip('\n')
      is_paused = raw.startswith('#PAUSED ')
      work = raw[len('#PAUSED '):] if is_paused else raw
      stripped = work.strip()
      if stripped and not stripped.startswith('#'):
        fields = stripped.split()
        if len(fields) >= 7 and fields[-1] in (request_mac, reversed_mac):
          matched = True
          result_paused = not is_paused
          new_lines.append((work if is_paused else '#PAUSED ' + work) + '\n')
          continue
      new_lines.append(line)
    atomic_write_lines(cron_filename, new_lines)
  return jsonify({'matched': matched, 'paused': result_paused})

@app.route('/check_status')
def check_status():
  ip_address = request.args.get('ip_address')
  test_type = request.args.get('test_type')
  if check_invalid_ip(ip_address or ''):
    return 'asleep'
  if is_computer_awake(ip_address, test_type):
    return 'awake'
  else:
    return 'asleep'

@app.route('/wol_or_sol_send', methods=['POST'])
def wol_or_sol_send():
  mac_address = request.form['mac_address']
  computers = load_computers()

  computer = next((c for c in computers if c['mac_address'] == mac_address), None)
  if computer is None:
    return generate_modal_html([f'Device with MAC address {mac_address} not found.'], 'Error'), 404
  ip_address = computer['ip_address']
  test_type = computer['test_type']

  messages = []
  if is_computer_awake(ip_address, test_type):
    reversed_mac_address = ':'.join(reversed(mac_address.split(':')))
    send_wol_packet(reversed_mac_address)
    title = "Shutdown"
    messages.append(f"Sleep On Lan Magic Packet Sent to {computer['name']}!")
    messages.append(Markup('See : <a href="https://github.com/Misterbabou/gptwol#configure-sleep-on-lan" target="_blank" rel="noopener noreferrer">how to configure Sleep on LAN</a>'))
  else:
    if l2_wol_packet:
      messages.append(f"Wake On Lan Mode: L2 Packet")
      send_l2_wol_packet(mac_address, l2_interface)
    else:
      messages.append(f"Wake On Lan Mode: L4 Packet")
      send_wol_packet(mac_address)
    title = "Wakeup"
    messages.append(f"Wake On Lan Magic Packet Sent to {computer['name']}!")

  return generate_modal_html(messages, title)

@app.route('/arp_scan', methods=['GET'])
def arp_scan():
  try:
    # Load the list of active computers
    computers = load_computers()
    active_mac_addresses = {computer['mac_address'] for computer in computers}

    command = ['arp-scan', '-lqx', '-t', str(arp_timeout)]
    if arp_interface:
      command += ['-I', arp_interface]

    result = subprocess.check_output(command, universal_newlines=True)
    lines = result.strip().split('\n')

    devices = []
    for line in lines:
      parts = line.split()
      if len(parts) >= 2:
        ip_address = parts[0]
        mac_address = parts[1]
        # Exclude MAC addresses that are already in the active computers list
        if mac_address not in active_mac_addresses:
          devices.append({'ip': ip_address, 'mac': mac_address})

    if not devices:
      return jsonify({'message': 'No new devices found.'})
    return jsonify(devices)

  except Exception as e:
    logger.warning(f"arp_scan failed: {e}")
    return jsonify({'message': 'ARP scan failed.'}), 500

def ensure_columns():
  import sqlite3
  con = None
  try:
    con = sqlite3.connect(db_path)
    cols = [r[1] for r in con.execute("PRAGMA table_info(computer)").fetchall()]
    if 'type' not in cols:
      con.execute("ALTER TABLE computer ADD COLUMN type VARCHAR(16)")
    if 'link' not in cols:
      con.execute("ALTER TABLE computer ADD COLUMN link VARCHAR(255)")
    con.commit()
  except Exception as e:
    logger.warning(f"ensure_columns failed: {e}")
  finally:
    if con is not None:
      con.close()

with app.app_context():
  # Serialize first-run schema init across gunicorn workers (avoid create_all race on a fresh DB)
  _init_lock = None
  try:
    _init_lock = open('/app/db/.init.lock', 'w')
    fcntl.flock(_init_lock, fcntl.LOCK_EX)
  except Exception:
    _init_lock = None
  try:
    db.create_all()
    migrate_txt_to_db()
    ensure_columns()
  except Exception as e:
    logger.warning(f"DB init issue (ignored): {e}")
  finally:
    if _init_lock is not None:
      try:
        fcntl.flock(_init_lock, fcntl.LOCK_UN)
        _init_lock.close()
      except Exception:
        pass
