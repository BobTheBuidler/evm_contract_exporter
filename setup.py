from setuptools import find_packages, setup

setup(
    name='evm_contract_exporter',
    packages=find_packages(),
    use_scm_version={
        "root": ".",
        "relative_to": __file__,
        "local_scheme": "no-local-version",
        "version_scheme": "python-simplified-semver",
    },
    description='a convenient common interface for exporting contract data and related metrics in various formats',
    author='BobTheBuidler',
    author_email='bobthebuidlerdefi@gmail.com',
    url='https://github.com/BobTheBuidler/evm_contract_exporter',
    license='MIT',
    setup_requires=[
        'setuptools_scm',
    ],
    package_data={
        'evm_contract_exporter': ['py.typed', '_docker/docker-compose.yaml'],
    },
    entry_points={
        'console_scripts': [
            'evm_contract_exporter=evm_contract_exporter._scripts.main:main',
        ],
    },
)

