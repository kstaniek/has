# -*- coding: utf-8 -*-
#
# Copyright (c) Klaudisz Staniek.
# See LICENSE for details.

import codecs

try:
    from setuptools import setup, Command
except ImportError:
    from distutils.core import setup, Command

from has.version import __version__


VERSION = __version__
DESCRIPTION = 'Home Automation System Library'
with codecs.open('README.rst', 'r', encoding='UTF-8') as readme:
    LONG_DESCRIPTION = ''.join(readme)


packages = [ 'has',
                 'has/utils',
                 'has/manager',
                 'has/manager/hc2',
                 ]
                 
install_requires = [ 'python-dateutil']
                 
                
setup(name='has',
      version           = VERSION,
      description       = DESCRIPTION,
      author            = 'Klaudiusz Staniek',
      author_email      = 'klaudiusz [at] staniek.name',
      url               = 'http://github.com/kstaniek/has',
      packages          = packages,
      install_requires  = install_requires,
     )