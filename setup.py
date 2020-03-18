from setuptools import setup

setup(
    name='sarfetcher',
    version='0.1',
    py_modules=['sarfetcher'],
    install_requires=[
        'Click',
        'requests',
        'sqlalchemy',
        'geoalchemy2',
        'numpy',
        'dateutils',
        'shapely'
    ],
    entry_points='''
        [console_scripts]
        sarfetcher=sarfetcher.main:cli
    ''',
)
