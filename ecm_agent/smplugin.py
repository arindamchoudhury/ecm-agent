#!/usr/bin/env python

from sys import argv, exit, exc_info, stdin, stderr
import inspect
import simplejson as json
import os, string, random

E_RUNNING_COMMAND = 253
E_COMMAND_NOT_DEFINED = 252

class SMPlugin():
    def _listCommands(self):
        for member in inspect.getmembers(self):
            #Retrieve method names starting with "cmd_" (commands)
            if member[0].startswith('cmd_') and inspect.ismethod(member[1]):
                command_name = member[0][4:]
                command_args = inspect.getargspec(member[1])[0][1:]
                print command_name, command_args

    def _runCommand(self, command_name):

        try:
            command = getattr(self, 'cmd_' + command_name)
        except:
            print >> stderr, "Command not defined (%s)" % command_name
            exit(E_COMMAND_NOT_DEFINED)
        #TODO:Rewrite argument checking with key requeriments parsing the json.
        #args_num = len(inspect.getargspec(command)[0][1:])
        #if (len(command_args) != args_num):
        #    print "Command requires %d arguments (%d provided)" % (
        #            args_num, len(command_args))
        #    exit(9)

        #Read command's arguments from stdin in json format.
        lines = []
        for line in stdin:
            lines.append(line)
        command_args = json.loads('\n'.join(lines))

        try:
            # conver returned data to json
            ret = command(**command_args)
            ret = json.dumps(ret)
            print ret
            return
        except:
            print >> stderr, "Error running command", exc_info()[:2]
            return E_RUNNING_COMMAND

    def run(self):
        if len(argv) == 1 or argv[1] == '':
            #Show available commands if no command selected
            return self._listCommands()
        else:
            command_name = argv[1]
            exit(self._runCommand(command_name))

    def _file_write(self,file,content=None):
        try:
            _path = os.path.dirname(file)
            if not os.path.exists(_path):
                os.mkdir(_path)

            f  = open(file,'w')
            if content:
                f.write(content)
            f.close()

        except:
            raise Exception("Unable to write file: %s" % file)

    def _file_read(self,file):
        try:
            if os.path.isfile(file):
                f  = open(file,'r')
                retval = f.read()
                f.close()
                return retval

        except:
            raise Exception("Unable to read file: %s" % file)

    def _secret_gen(self):
        chars = string.ascii_uppercase + string.digits  + '!@#$%^&*()'
        return ''.join(random.choice(chars) for x in range(60))
