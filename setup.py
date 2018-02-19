import os
from setuptools import find_packages, setup

with open(os.path.join(os.path.dirname(__file__),'README.md')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__),os.pardir)))

setup(
    name='django-chado',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    license='BSD License',
    description='DjangoChado is a Django app that contains tools to interact with a Chado database.',
    long_description=README,
    url='https://bitbucket.org/azneto/djangochado',
    author='Adhemar',
    author_email='azneto@gmail.com',
    classifiers=[
        'Environment :: Command Line',
        'Framework :: Django',
        'Programming Language :: Python'
        'Programming Language :: Python :: 3'
    ],
    scripts=[
        'bin/fixChadoModel.py'
    ],
    zip_safe=False,
)
