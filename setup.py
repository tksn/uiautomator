#!/usr/bin/env python
# -*- coding: utf-8 -*-
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


requires = [
    'requests>=2.11.1',
    #'tksn.adb==0.1.0.dev2'
]
test_requires = [
    'nose>=1.0',
    'mock>=1.0.1',
    'coverage>=3.6'
]

version = '0.0.1'

setup(
    name='uiautomatorminus',
    version=version,
    description='Python Wrapper for Android UiAutomator test tool',
    long_description='Python wrapper for Android uiautomator tool.',
    author='Takeshi Naoi',
    author_email='tksnaoi+github@gmail.com',
    url='https://github.com/tksn/uiautomatorminus',
    download_url='https://github.com/tksn/uiautomatorminus/tarball/%s' % version,
    keywords=[
        'testing', 'android', 'uiautomator'
    ],
    install_requires=requires,
    tests_require=test_requires,
    test_suite="nose.collector",
    packages=['uiautomatorminus'],
    package_data={
        'uiautomatorminus': [
            'uiautomatorminus/libs/uiautomatorminus_test.apk',
            'uiautomatorminus/libs/uiautomatorminus.apk'
        ]
    },
    dependency_links=[
        'https://bitbucket.org/tksn/tksn.adb/get/master.zip#egg=tksn.adb-0.1.0.dev2'
    ],
    include_package_data=True,
    license='MIT',
    platforms='any',
    classifiers=(
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Testing'
    )
)
