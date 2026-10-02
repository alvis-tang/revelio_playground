"""Remote environment, credentials, and persistent job management."""
import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def config():
    return json.loads((ROOT / '.klc/config.json').read_text())


def stata_command(c):
    module = c.get('stata_module', '')
    prefix = f'module load {shlex.quote(module)} && ' if module else ''
    probe = prefix + '(command -v stata-mp || command -v stata-se || command -v stata)'
    result = subprocess.run(['bash', '-lc', probe], capture_output=True, text=True)
    executable = result.stdout.strip().splitlines()
    if result.returncode or not executable:
        raise ValueError('Stata unavailable. Set stata_module with ./klc setup and bootstrap again.')
    return prefix, executable[-1]


def initialize(c):
    for folder in ('data', 'proc', 'results', 'tables', 'logs', 'logs/jobs'):
        (ROOT / folder).mkdir(exist_ok=True)
    if not c.get('stata_module'):
        modules = subprocess.run(['bash', '-lc', 'module -t avail stata'],
                                 capture_output=True, text=True)
        matches = re.findall(r'(?im)^\s*(stata[\w.-]*/[\w.-]+)', modules.stdout + modules.stderr)
        if matches:
            c['stata_module'] = sorted(matches)[-1]
            save(ROOT / '.klc/config.json', c)
    try:
        print('Stata:', stata_command(c)[1])
    except ValueError as exc:
        print(exc)
    print('Environment ready. Run ./klc credentials, then ./klc doctor.')


def credentials(c):
    def escape(value):
        return value.replace('\\', '\\\\').replace(':', '\\:')
    password = getpass.getpass('WRDS password (stored only in KLC ~/.pgpass): ')
    if not password or '\n' in password or '\r' in password:
        raise ValueError('Password must be nonempty and contain no newlines.')
    path = Path.home() / '.pgpass'
    prefix = 'wrds-pgdata.wharton.upenn.edu:9737:wrds:' + escape(c['wrds_username']) + ':'
    lines = path.read_text().splitlines() if path.exists() else []
    lines = [line for line in lines if not line.startswith(prefix)]
    # Create privately from the first write, not merely chmod afterwards.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write('\n'.join([*lines, prefix + escape(password)]) + '\n')
    print('Credentials saved. WRDS may request Duo approval during connection.')


def job_path(job):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', job):
        raise ValueError('Invalid job ID.')
    return ROOT / 'logs/jobs' / job


def execute(job):
    directory = job_path(job)
    record = json.loads((directory / 'job.json').read_text())
    record.update(status='running', pid=os.getpid())
    if os.environ.get('SLURM_JOB_ID'):
        record['scheduler_id'] = os.environ['SLURM_JOB_ID']
    save(directory / 'job.json', record)
    with (directory / 'output.log').open('a') as log:
        result = subprocess.run(['bash', '-lc', record['command']], cwd=directory, stdout=log, stderr=subprocess.STDOUT)
    failed_stata = False
    if record['language'] == 'stata':
        stata_logs = [p for p in directory.glob('*.log') if p.name != 'output.log']
        failed_stata = not stata_logs or any(
            re.search(r'(?m)^\s*r\(\d+\);\s*$', p.read_text(errors='replace')) for p in stata_logs)
    record.update(status='failed' if result.returncode or failed_stata else 'complete',
                  exit_code=result.returncode, stata_log_error=bool(failed_stata))
    save(directory / 'job.json', record)
    return 1 if record['status'] == 'failed' else 0


def launch(c, arguments, submit=False):
    parser = argparse.ArgumentParser(prog='klc submit' if submit else 'klc run')
    parser.add_argument('--cpus', type=int, default=1)
    parser.add_argument('--memory', default='8G')
    parser.add_argument('--time', default='00:30:00')
    parser.add_argument('language', choices=['python', 'stata'])
    parser.add_argument('script')
    parser.add_argument('args', nargs=argparse.REMAINDER)
    ns = parser.parse_args(arguments)
    script = (ROOT / ns.script).resolve()
    if not script.is_file() or not script.is_relative_to(ROOT):
        raise ValueError('Script must exist inside the remote project.')
    if ns.cpus < 1 or (not submit and ns.cpus > 24):
        raise ValueError('Invalid core count; direct KLC jobs must use at most 24 cores.')
    if submit:
        if not shutil.which('sbatch') or not c.get('slurm_account') or not c.get('slurm_partition'):
            raise ValueError('Reserve unavailable or unconfigured. Set account and partition using setup; no direct fallback.')
        # Ask the scheduler to validate the actual account, partition, and resources.
        resources = ['--account=' + c['slurm_account'], '--partition=' + c['slurm_partition'],
                     '--cpus-per-task=' + str(ns.cpus), '--mem=' + ns.memory, '--time=' + ns.time]
        subprocess.run(['sbatch', '--test-only', *resources, '--wrap=true'], check=True)
    elif not shutil.which('tmux'):
        raise ValueError('tmux unavailable.')
    job = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:6]
    directory = job_path(job)
    directory.mkdir(parents=True)
    if ns.language == 'python':
        command = shlex.join([str(ROOT / '.venv/bin/python'), str(script), *ns.args])
    else:
        prefix, executable = stata_command(c)
        command = prefix + shlex.join([executable, '-q', '-b', 'do', str(script), *ns.args])
    # Paths are explicit; scripts can use KLC_ROOT instead of assuming the working directory.
    exports = {'KLC_ROOT': str(ROOT), 'OMP_NUM_THREADS': str(ns.cpus),
               'OPENBLAS_NUM_THREADS': str(ns.cpus), 'MKL_NUM_THREADS': str(ns.cpus),
               'PYTHONUNBUFFERED': '1'}
    command = 'export ' + ' '.join(k + '=' + shlex.quote(v) for k, v in exports.items()) + '; ' + command
    save(directory / 'job.json', dict(id=job, language=ns.language, command=command,
         backend='slurm' if submit else 'tmux', status='pending', script=str(script)))
    prefix = f'module load {shlex.quote(c["python_module"])} && ' if c.get('python_module') else ''
    worker = prefix + shlex.join([str(ROOT / '.venv/bin/python'), str(ROOT / 'tools/remote.py'), '_execute', job])
    if submit:
        result = subprocess.check_output(['sbatch', '--parsable', *resources,
            '--output=' + str(directory / 'scheduler.log'),
            '--wrap=' + shlex.join(['bash', '-lc', worker])], text=True).strip()
        # Separate file avoids racing the worker's state updates.
        (directory / 'scheduler_id').write_text(result.split(';')[0])
    else:
        subprocess.run(['tmux', 'new-session', '-d', '-s', 'klc-' + job,
                        shlex.join(['bash', '-lc', worker])], check=True)
    print(job)


def main():
    os.chdir(ROOT)
    command, *args = sys.argv[1:]
    c = config()
    if command == 'initialize':
        initialize(c)
    elif command == 'credentials':
        credentials(c)
    elif command in ('run', 'submit'):
        launch(c, args, submit=command == 'submit')
    elif command == '_execute':
        sys.exit(execute(args[0]))
    elif command == 'wrds':
        from wrds_data import main as data_main
        data_main(args)
    elif command == 'doctor':
        print('Project:', ROOT, 'writable:', os.access(ROOT, os.W_OK))
        print('tmux:', shutil.which('tmux'), 'SLURM:', shutil.which('sbatch'))
        print('Reserve account:', c.get('slurm_account') or 'unconfigured',
              'partition:', c.get('slurm_partition') or 'unconfigured')
        try:
            print('Stata:', stata_command(c)[1])
        except ValueError as exc:
            print(exc)
        from wrds_data import connection
        with connection() as conn:
            print('WRDS:', conn.raw_sql('SELECT 1 AS connected').to_string(index=False))
    elif command == 'status':
        paths = [job_path(args[0]) / 'job.json'] if args else sorted((ROOT / 'logs/jobs').glob('*/job.json'))
        for path in paths:
            record = json.loads(path.read_text())
            scheduler_file = path.parent / 'scheduler_id'
            if scheduler_file.exists():
                record['scheduler_id'] = scheduler_file.read_text().strip()
            print(json.dumps(record, indent=2))
            if record['backend'] == 'slurm' and record.get('scheduler_id'):
                subprocess.run(['squeue', '-j', record['scheduler_id']])
                if shutil.which('sacct'):
                    subprocess.run(['sacct', '-j', record['scheduler_id'],
                                    '--format=JobID,State,ExitCode', '--noheader'])
            elif record['status'] in ('pending', 'running'):
                result = subprocess.run(['tmux', 'has-session', '-t', 'klc-' + record['id']], capture_output=True)
                if result.returncode:
                    print('Worker missing: interrupted; inspect logs before rerunning.')
    elif command == 'logs':
        for path in sorted(job_path(args[0]).glob('*.log')):
            print(f'--- {path.name} ---')
            subprocess.run(['tail', '-n', '80', str(path)], check=True)
    elif command == 'cancel':
        directory = job_path(args[0])
        record = json.loads((directory / 'job.json').read_text())
        scheduler_file = directory / 'scheduler_id'
        if scheduler_file.exists():
            record['scheduler_id'] = scheduler_file.read_text().strip()
        if record['status'] in ('complete', 'failed', 'cancelled'):
            raise ValueError('Job already finished.')
        if record['backend'] == 'slurm':
            subprocess.run(['scancel', record['scheduler_id']], check=True)
        else:
            subprocess.run(['tmux', 'kill-session', '-t', 'klc-' + record['id']], check=True)
        record['status'] = 'cancelled'
        save(directory / 'job.json', record)
    else:
        raise ValueError('Unknown remote command.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, KeyboardInterrupt) as exc:
        print(f'KLC: {exc}', file=sys.stderr)
        sys.exit(1)
