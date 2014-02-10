# -*- coding:utf-8 -*-

# Copyright (C) 2012 Juan Carlos Moreno <juancarlos.moreno at ecmanaged.com>
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import os
import string
import random
import re
import platform
import urllib2

from subprocess import Popen, PIPE
from shlex import split
from threading import Thread
from time import sleep

from time import time
from base64 import b64decode

import twisted.python.procutils as procutils

import simplejson as json
import sys

if not sys.platform.startswith("win32"):
    import fcntl

_ETC = '/etc'
_DIR = '/etc/ecmanaged'
_ENV_FILE = _DIR + '/ecm_env'
_INFO_FILE = _DIR + '/node_info'

_DEFAULT_GROUP_LINUX = 'root'
_DEFAULT_GROUP_WINDOWS = 'Administrators'

_FLUSH_WORKER_SLEEP_TIME = 0.2

__all__ = []


def is_windows():
        """ Returns True if is a windows system
        """
        if sys.platform.startswith("win32"):
            return True

        return False


def file_write(file_path, content=None):
    """ Writes a file
    """
    try:
        if content:
            _path = os.path.dirname(file_path)
            if not os.path.exists(_path):
                mkdir_p(_path)

            f = open(file_path, 'w')
            f.write(content)
            f.close()

    except:
        raise Exception("Unable to write file: %s" % file)


def file_read(file_path):
    """ Reads a file and returns content
    """
    try:
        if os.path.isfile(file_path):
            f = open(file_path, 'r')
            retval = f.read()
            f.close()
            return retval

    except:
        raise Exception("Unable to read file: %s" % file)


def random_charts(length=60):
    """ Generates random chars
    """
    chars = string.ascii_uppercase + string.digits + '!@#$%^&*()'
    return ''.join(random.choice(chars) for x in range(length))


def clean_stdout(output):
    """ Remove color chars from output
    """
    try:
        r = re.compile("\033\[[0-9;]*m", re.MULTILINE)
        return r.sub('', output)
    except:
        return output


def download_file(url, file, user=None, passwd=None):
    """
    Downloads a remote content
    """
    try:
        if user and passwd:
            password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
            password_manager.add_password(None, url, user, passwd)

            auth_manager = urllib2.HTTPBasicAuthHandler(password_manager)
            opener = urllib2.build_opener(auth_manager)

            # ...and install it globally so it can be used with urlopen.
            urllib2.install_opener(opener)

        req = urllib2.urlopen(url.replace("'", ""))
        CHUNK = 256 * 10240
        with open(file, 'wb') as fp:
            while True:
                chunk = req.read(CHUNK)
                if not chunk: break
                fp.write(chunk)
    except:
        return False

    return file


def chmod(filename, mode):
    """
    chmod a file
    """
    try:
        os.chmod(filename, mode)
        return True

    except:
        return False


def which(command):
    """
    search executable on path
    """
    found = procutils.which(command)

    try:
        cmd = found[0]
    except IndexError:
        return False

    return cmd


def chown(path, user, group, recursive=False):
    """
    chown a file or path
    """
    try:
        from pwd import getpwnam
        from grp import getgrnam

        uid = gid = 0
        try:
            uid = getpwnam(user)[2]
        except KeyError:
            pass

        try:
            gid = getgrnam(group)[2]
        except KeyError:
            pass

        if recursive:
            # Recursive chown
            if not os.path.isdir(path):
                return False

            for root, dirs, files in os.walk(path):
                os.chown(os.path.join(path, root), uid, gid)
                for f in files:
                    os.chown(os.path.join(path, root, f), uid, gid)
        else:
            # Just file or path
            os.chown(path, uid, gid)

    except:
        return False

    return True


def install_package(packages, update=True):
    """
    Install packages
    """
    try:
        envars = {}
        distribution, _version = get_distribution()

        if distribution.lower() in ['debian', 'ubuntu']:
            envars['DEBIAN_FRONTEND'] = 'noninteractive'

            if update: execute_command(['apt-get', '-y', '-qq', 'update'])
            command = ['apt-get',
                       '-o',
                       'Dpkg::Options::=--force-confold',
                       '--allow-unauthenticated',
                       '--force-yes',
                       '-y',
                       '-qq',
                       'install',
                       packages]

        elif distribution.lower() in ['centos', 'redhat', 'fedora', 'amazon']:
            if update: execute_command(['yum', '-y', 'clean', 'all'])
            command = ['yum',
                       '-y',
                       '--nogpgcheck',
                       'install',
                       packages]

        elif distribution.lower() in ['suse']:
            command = ['zypper',
                       '--non-interactive',
                       '--auto-agree-with-licenses',
                       'install',
                       packages]

        elif distribution.lower() in ['arch']:
            if update: execute_command(['pacman', '-Sy'])
            if update: execute_command(['pacman', '-S', '--noconfirm', 'pacman'])
            command = ['pacman',
                       '-S',
                       '--noconfirm',
                       packages]

        else:
            return 1, '', "Distribution not supported: %s" % distribution

        return execute_command(command, envars=envars)

    except Exception as e:
        return 1, '', "Error installing packages %s" % e


def execute_file(file, args=None, stdin=None, runas=None, workdir=None, envars=None):
    """
    Execute a script file
    """
    if os.path.isfile(file):
        os.chmod(file, 0700)
        e = ECMExec()
        return e.command([file], args, stdin, runas, workdir, envars)

    return 255, '', 'Script file not found'


def execute_command(command, args=None, stdin=None, runas=None, workdir=None, envars=None):
    """
    Execute command and flush stdout/stderr using threads
    """
    e = ECMExec()
    return e.command(command, args, stdin, runas, workdir, envars)


def envars_decode(coded_envars=None):
    """ Decode base64/json envars """
    envars = None
    try:
        if coded_envars:
            envars = b64decode(coded_envars)
            envars = json.loads(envars)
            for var in envars.keys():
                if not envars[var]: envars[var] = ''
                envars[var] = encode(envars[var])

    except:
        pass
    return envars


def write_envars_facts(envars=None, facts=None):
    """
    Writes env and facts file variables
    """
    if envars and is_dict(envars):
        try:
            content_env = ''
            for var in sorted(envars.keys()):
                content_env += "export " + str(var) + '="' + encode(envars[var]) + "\"\n"
            file_write(_ENV_FILE, content_env)

        except:
            return False

    if facts and is_dict(envars):
        try:
            content_facts = ''
            for var in sorted(facts.keys()):
                content_facts += str(var) + ':' + encode(facts[var]) + "\n"
            file_write(_INFO_FILE, content_facts)

        except:
            return False

    return True


def renice_me(nice):
    """
    Changes execution priority
    """
    if nice and is_number(nice):
        try:
            os.nice(int(nice))
            return (0)

        except:
            return (1)
    else:
        return (1)


def is_number(s):
    """ Helper function """
    try:
        float(s)
        return True
    except ValueError:
        return False


def output(string):
    """ Helper function """
    return '[' + str(time()) + '] ' + str(string) + "\n"

def format_output(out, stdout, stderr):
    """ Helper function """
    format_out = {}
    format_out['out'] = out
    format_out['stdout'] = stdout
    format_out['stderr'] = stderr

    return format_out


def mkdir_p(path):
    """ Recursive Mkdir """
    try:
        if not os.path.isdir(path):
            os.makedirs(path)
    except OSError:
        pass


def utime():
    """ Helper function: microtime """
    str_time = str(time()).replace('.', '_')
    return str_time


def is_dict(obj):
    """Check if the object is a dictionary."""
    return isinstance(obj, dict)


def is_list(obj):
    """Check if the object is a list"""
    return isinstance(obj, list)


def is_string(obj):
    """Check if the object is a list"""
    if isinstance(obj, str) or isinstance(obj, unicode):
        return True

    return False


def encode(string):
    try:
        string = string.encode('utf-8')
        return string
    except:
        return str(string)


def split_path(path):
    components = []
    while True:
        (path,tail) = os.path.split(path)
        if tail == "":
            components.reverse()
            return components
        components.append(tail)


def get_distribution():
    distribution, version = None, None

    try:
        (distribution, version, _id) = platform.dist()
    except:
        pass

    if not distribution:
        _release_filename = re.compile(r'(\w+)[-_](release|version)')
        _release_version = re.compile(r'(.*?)\s.*\s+release\s+(.*)')

        try:
            etc_files = os.listdir(_ETC)

        except os.error:
            # Probably not a Unix system
            return distribution, version

        for etc_file in etc_files:
            m = _release_filename.match(etc_file)
            if m is None or not os.path.isfile(_ETC + '/' + etc_file):
                continue

            try:
                f = open(_ETC + '/' + etc_file, 'r')
                first_line = f.readline()
                f.close()
                m = _release_version.search(first_line)

                if m is not None:
                    distribution, version = m.groups()
                    break

            except:
                pass

    return distribution, version


class ECMExec:
    def _init__(self):
        self.thread_stdout = ''
        self.thread_stderr = ''
        self.thread_run = 1

    def command(self, command, args=None, stdin=None, runas=None, workdir=None, envars=None):
        """
        Execute command and flush stdout/stderr using threads
        """

        # Prepare environment variables
        if not envars or not is_dict(envars):
            envars = {}

        env = os.environ.copy()
        env = dict(env.items() + envars.items())

        # Create a full command line to split later
        if is_list(command):
            command = ' '.join(command)

        if workdir:
            workdir = os.path.abspath(workdir)

        # create command array and add args
        command = split(command)
        if args and is_list(args):
            for arg in args:
                command.append(arg)

        if runas and not is_windows():
            # dont use su - xxx or env variables will not be available
            command = ['su', runas, '-c', ' '.join(map(str, command))]

            # :TODO: Runas for windows :S

        try:
            p = Popen(
                command,
                env=env,
                bufsize=0, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                cwd=workdir,
                universal_newlines=True,
                close_fds=(os.name == 'posix')
            )

            # Write stdin if set
            if stdin:
                p.stdin.write(stdin)
                p.stdin.flush()

            p.stdin.close()

            if is_windows():
                stdout, stderr = p.communicate()
                return p.wait(), stdout, stderr

            else:
                thread = Thread(target=self._thread_flush_worker, args=[p.stdout, p.stderr])
                thread.daemon = True
                thread.start()

                # Wait for end
                retval = p.wait()

                # Ensure to get last output from Thread
                sleep(_FLUSH_WORKER_SLEEP_TIME * 2)

                # Stop Thread
                self.thread_run = 0
                thread.join(timeout=1)

                return retval, self.thread_stdout, self.thread_stderr

        except OSError, e:
            return e[0], '', "Execution failed: %s" % e[1]

        except Exception as e:
            return 255, '', 'Unknown error'

    def _thread_flush_worker(self, str_stdout, str_stderr):
        """
        needs to be in a thread so we can read the stdout w/o blocking
        """
        while self.thread_run:
            # Avoid Exception in thread Thread-1 (most likely raised during interpreter shutdown):
            try:
                output = clean_stdout(self._non_block_read(str_stdout))
                if output:
                    self.thread_stdout += output
                    sys.stdout.write(output)

                output = clean_stdout(self._non_block_read(str_stderr))
                if output:
                    self.thread_stderr += output
                    sys.stderr.write(output)

                sleep(_FLUSH_WORKER_SLEEP_TIME)

            except:
                pass

    def _non_block_read(self, output):
        """
        even in a thread, a normal read with block until the buffer is full
        """
        try:
            fd = output.fileno()
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            return output.read()

        except:
            return ''

