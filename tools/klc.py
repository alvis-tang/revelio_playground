"""Local KLC connection and deployment commands (standard library only)."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / '.klc/config.json'


def shell(args):
    return shlex.join([str(x) for x in args])


def load():
    if not CONFIG.exists():
        raise ValueError('Run ./klc setup first.')
    return json.loads(CONFIG.read_text())


def ssh(config, command=None, interactive=False, **kwargs):
    args = ['ssh'] + (['-t'] if interactive else []) + [config['alias']]
    if command:
        args += [shell(['bash', '-lc', command])]
    return subprocess.run(args, check=True, **kwargs)


def setup():
    old = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    def ask(key, label, default=''):
        value = input(f'{label} [{old.get(key, default)}]: ').strip()
        return '' if value == '-' else value or old.get(key, default)
    config = {
        'netid': ask('netid', 'Northwestern NetID'),
        'host': ask('host', 'KLC hostname', 'klc0305.quest.northwestern.edu'),
        'project': ask('project', 'Existing absolute project-storage directory'),
        'wrds_username': ask('wrds_username', 'WRDS username'),
        'alias': ask('alias', 'SSH alias', 'klc-revelio'),
        'python_module': ask('python_module', 'Python module (blank uses remote python3)'),
        'stata_module': ask('stata_module', 'Stata module (blank auto-discovers)'),
        'slurm_account': ask('slurm_account', 'Reserve account (blank if unknown)'),
        'slurm_partition': ask('slurm_partition', 'Reserve partition (blank if unknown)'),
    }
    for key in ('netid', 'host', 'alias', 'wrds_username'):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', config[key]):
            raise ValueError(f'Invalid {key}.')
    if not config['project'].startswith('/') or not config['wrds_username']:
        raise ValueError('An absolute project path and WRDS username are required.')
    config['remote_root'] = config['project'].rstrip('/') + '/revelio_playground'
    config['repository'] = subprocess.check_output(
        ['git', 'remote', 'get-url', 'origin'], cwd=ROOT, text=True).strip()
    sshdir = Path.home() / '.ssh'
    sshdir.mkdir(mode=0o700, exist_ok=True)
    sshconfig = sshdir / 'config'
    existing = sshconfig.read_text() if sshconfig.exists() else ''
    start, end = '# BEGIN revelio_playground KLC', '# END revelio_playground KLC'
    entry = (f'{start}\nHost {config["alias"]}\n'
             f'  HostName {config["host"]}\n  User {config["netid"]}\n'
             f'  ServerAliveInterval 30\n  ServerAliveCountMax 3\n{end}\n')
    key = Path.home() / '.ssh/id_ed25519_klc'
    if key.exists():
        entry = entry.replace(end, f'  IdentityFile "{key}"\n  AddKeysToAgent yes\n  UseKeychain yes\n{end}')
    if start in existing:
        existing = re.sub(re.escape(start) + r'.*?' + re.escape(end) + r'\n?',
                          lambda _: entry, existing, flags=re.S)
    else:
        # Check effective configuration too, including user Include directives.
        result = subprocess.run(['ssh', '-G', config['alias']], capture_output=True, text=True)
        effective = dict(line.split(' ', 1) for line in result.stdout.splitlines() if ' ' in line)
        if effective.get('hostname', config['alias']) != config['alias']:
            raise ValueError('SSH alias already configured elsewhere. Choose another alias.')
        existing = entry + '\n' + existing  # Host * defaults must follow this entry.
    sshconfig.write_text(existing)
    sshconfig.chmod(0o600)
    CONFIG.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(config, indent=2) + '\n')
    CONFIG.chmod(0o600)
    print('Saved. Next: ./klc doctor; ./klc bootstrap; ./klc credentials')


def remote_command(config, args):
    root = config['remote_root']
    module = config.get('python_module')
    prefix = f'module load {shlex.quote(module)} && ' if module else ''
    return (f'cd {shlex.quote(root)} && {prefix}' +
            shell([root + '/.venv/bin/python', 'tools/remote.py', *args]))


def bootstrap(config):
    project, root = config['project'], config['remote_root']
    command = (f'set -e; test -d {shlex.quote(project)}; test -w {shlex.quote(project)}; '
               f'if test ! -e {shlex.quote(root)}; then '
               + shell(['git', 'clone', config['repository'], root]) + '; fi; '
               + shell(['test', '-d', root + '/.git']))
    ssh(config, command)
    # Upload only toolkit files, including before their first commit. Never delete remote files.
    files = ['klc', 'requirements-klc.txt', 'tools/klc.py', 'tools/remote.py',
             'tools/wrds_data.py', 'examples/revelio_positions.sql',
             'examples/stata_smoke.do', 'examples/python_smoke.py', 'examples/analyze_revelio.do']
    subprocess.run(['rsync', '-av', '--relative', *files,
                    config['alias'] + ':' + shlex.quote(root + '/')], cwd=ROOT, check=True)
    payload = json.dumps(config)
    writer = ('import pathlib,sys; p=pathlib.Path(".klc/config.json"); '
              'p.parent.mkdir(mode=448,exist_ok=True); p.write_text(sys.stdin.read()); p.chmod(384)')
    prefix = f'module load {shlex.quote(config["python_module"])} && ' if config.get('python_module') else ''
    ssh(config, f'cd {shlex.quote(root)} && {prefix}' + shell(['python3', '-c', writer]),
        input=payload, text=True)
    version_check = shell(['python3', '-c', 'import sys; assert (3,9) <= sys.version_info[:2] <= (3,12), "Use a Python 3.9-3.12 module for WRDS compatibility"'])
    ssh(config, f'cd {shlex.quote(root)} && {prefix}' + version_check + ' && '
        'python3 -m venv .venv && .venv/bin/python -m pip install -r requirements-klc.txt && '
        '.venv/bin/python tools/remote.py initialize', interactive=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['setup', 'connect', 'code', 'doctor', 'bootstrap',
        'credentials', 'key', 'run', 'submit', 'status', 'logs', 'cancel', 'wrds'])
    parser.add_argument('args', nargs=argparse.REMAINDER)
    ns = parser.parse_args()
    if ns.command == 'setup':
        setup()
        return
    c = load()
    if ns.command == 'connect':
        ssh(c, interactive=True)
    elif ns.command == 'code':
        code = shutil.which('code') or '/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code'
        subprocess.run([code, '--install-extension', 'ms-vscode-remote.remote-ssh'], check=True)
        subprocess.run([code, '--folder-uri', f'vscode-remote://ssh-remote+{c["alias"]}{quote(c["remote_root"])}'], check=True)
    elif ns.command == 'bootstrap':
        bootstrap(c)
    elif ns.command == 'key':
        key = Path.home() / '.ssh/id_ed25519_klc'
        if not key.exists():
            subprocess.run(['ssh-keygen', '-t', 'ed25519', '-f', str(key)], check=True)
        ssh(c, 'umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; '
            'IFS= read -r key; grep -qxF "$key" ~/.ssh/authorized_keys || '
            'printf "%s\\n" "$key" >> ~/.ssh/authorized_keys',
            input=key.with_suffix('.pub').read_text(), text=True)
        subprocess.run(['ssh-add', '--apple-use-keychain', str(key)], check=True)
        sshconfig = Path.home() / '.ssh/config'
        contents = sshconfig.read_text()
        start, end = '# BEGIN revelio_playground KLC', '# END revelio_playground KLC'
        block = re.search(re.escape(start) + r'.*?' + re.escape(end), contents, flags=re.S)
        if block and 'IdentityFile' not in block.group():
            updated = block.group().replace(end, f'  IdentityFile "{key}"\n  AddKeysToAgent yes\n  UseKeychain yes\n{end}')
            sshconfig.write_text(contents[:block.start()] + updated + contents[block.end():])
        print('Key installed and loaded into SSH agent.')
    elif ns.command == 'doctor':
        ssh(c, 'hostname; command -v python3; command -v tmux; command -v sbatch; '
            + shell(['test', '-w', c['project']]) + ' && df -h ' + shlex.quote(c['project']) + '; '
            + f'if test -x {shlex.quote(c["remote_root"] + "/.venv/bin/python")}; then '
            + remote_command(c, ['doctor']) + '; else echo "Run ./klc bootstrap next."; fi', interactive=True)
    else:
        ssh(c, remote_command(c, [ns.command, *ns.args]), interactive=ns.command in ('credentials', 'wrds'))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, KeyboardInterrupt) as exc:
        print(f'KLC: {exc}', file=sys.stderr)
        sys.exit(1)
