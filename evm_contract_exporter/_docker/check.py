
import subprocess
from functools import lru_cache


def check_docker() -> None:
    try:
        subprocess.check_output(['docker', '--version'])
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError('Docker is not installed. You must install Docker before using evm_contract_exporter.') from None

def check_docker_compose() -> None:
    try:
        subprocess.check_output(['docker-compose', '--version'])
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.check_output(['docker', 'compose', '--version'])
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError('Docker Compose is not installed. You must install Docker Compose before using evm_contract_exporter.') from None

@lru_cache
def check_system() -> None:
    print('checking your computer for docker')
    check_docker()
    print('docker found!')
    print('checking your computer for docker-compose')
    check_docker_compose()
    print('docker-compose found!')
