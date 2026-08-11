import paramiko
import sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('76.13.180.80', username='root', password='6yfRBK?t;9+u/eQd', timeout=15)

def run_cmd(cmd, timeout=30):
    print(f'>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if out:
        sys.stdout.buffer.write(out.encode('utf-8', errors='replace'))
        sys.stdout.buffer.write(b'\n')
    if err:
        sys.stdout.buffer.write(b'STDERR: ')
        sys.stdout.buffer.write(err.encode('utf-8', errors='replace'))
        sys.stdout.buffer.write(b'\n')
    sys.stdout.buffer.write(f'[exit: {exit_code}]\n'.encode())
    sys.stdout.buffer.write(b'\n')
    sys.stdout.buffer.flush()
    return exit_code

print("=" * 60)
print("CHECK 1: Listening ports")
print("=" * 60)
run_cmd('ss -tlnp | grep -E "8080|8000|8001|9100"')

print("=" * 60)
print("CHECK 2: Firewall (ufw)")
print("=" * 60)
run_cmd('ufw status 2>/dev/null || echo "ufw not installed"')

print("=" * 60)
print("CHECK 3: iptables rules")
print("=" * 60)
run_cmd('iptables -L INPUT -n --line-numbers 2>/dev/null | head -20 || echo "no iptables"')

print("=" * 60)
print("CHECK 4: nginx reverse proxy")
print("=" * 60)
run_cmd('nginx -t 2>&1 || echo "no nginx"')
run_cmd('ls /etc/nginx/sites-enabled/ 2>/dev/null || echo "no sites-enabled"')
run_cmd('cat /etc/nginx/sites-enabled/* 2>/dev/null | head -80 || echo "no nginx config"')

print("=" * 60)
print("CHECK 5: curl from VPS to confirm services respond")
print("=" * 60)
run_cmd('curl -s -o /dev/null -w "trading(8080): %{http_code}\\n" http://127.0.0.1:8080/docs')
run_cmd('curl -s -o /dev/null -w "auth(8000): %{http_code}\\n" http://127.0.0.1:8000/health')
run_cmd('curl -s -o /dev/null -w "ai(8001): %{http_code}\\n" http://127.0.0.1:8001/docs')

print("=" * 60)
print("CHECK 6: Public IP")
print("=" * 60)
run_cmd('curl -s ifconfig.me 2>/dev/null || hostname -I')

ssh.close()
print("\nDone!")
