#!/usr/bin/python3
import os, re
from samba.gpclass import gp_pol_ext, gp_file_applier,
    register_gp_extension, unregister_gp_extension,
    list_gp_extensions
from tempfile import NamedTemporaryFile
from samba.gp.util.logging import log
from samba import getopt as options
import optparse

intro = '''
### autogenerated by samba
#
# This file is generated by the gp_scripts_ext Group Policy
# Client Side Extension. To modify the contents of this file,
# modify the appropriate Group Policy objects which apply
# to this machine. DO NOT MODIFY THIS FILE DIRECTLY.
#

'''

class gp_scripts_ext(gp_pol_ext, gp_file_applier):
    def __str__(self):
        return 'Unix Settings/Scripts'

    def process_group_policy(self, deleted_gpo_list,
                             changed_gpo_list):

        # Iterate over GPO guids and their previous settings,
        # reverting changes made by this GPO.
        for guid, settings in deleted_gpo_list:

            # Use the unapply() function from the base class
            # gp_file_applier to remove the files.
            if str(self) in settings:
                for attribute, script in \
                        settings[str(self)].items():
                    # Delete the applied policy
                    self.unapply(guid, attribute, script)

        # Iterate over GPO objects, applying new policies found
        # in the SYSVOL
        for gpo in changed_gpo_list:
            if gpo.file_sys_path:
                reg_key = 'Software\\Policies\\' + \
                          'Samba\\Unix Settings'
                sections = { '%s\\Daily Scripts' % reg_key :
                               '/etc/cron.daily',
                             '%s\\Monthly Scripts' % reg_key :
                               '/etc/cron.monthly',
                             '%s\\Weekly Scripts' % reg_key :
                               '/etc/cron.weekly',
                             '%s\\Hourly Scripts' % reg_key :
                               '/etc/cron.hourly'
                           }

                # Load the contents of the Registry.pol
                # from the SYSVOL
                pol_file = 'MACHINE/Registry.pol'
                path = os.path.join(gpo.file_sys_path, pol_file)
                pol_conf = self.parse(path)
                if not pol_conf:
                    continue

                # Gather the list of policies to apply
                policies = {}
                for e in pol_conf.entries:
                    if e.keyname in sections.keys() and \
                            e.data.strip():
                        if e.keyname not in policies:
                            policies[e.keyname] = []
                        policies[e.keyname].append(e.data)

                # Specify the applier function, which will be
                # used to apply the policy.
                def applier_func(keyname, entries):
                    ret = []
                    cron_dir = sections[e.keyname]
                    for data in entries:
                        with NamedTemporaryFile(prefix='gp_',
                                                mode="w+",
                                                delete=False,
                                                dir=cron_dir) as f:
                            contents = '#!/bin/sh\n%s' % intro
                            contents += '%s\n' % data
                            f.write(contents)
                            os.chmod(f.name, 0o700)
                            ret.append(f.name)
                    return ret

                # For each policy in the Registry.pol,
                # apply the settings
                for keyname, entries in policies.items():
                    # Each GPO applies only one set of each type
                    # of script, so so the attribute matches the
                    # keyname.
                    attribute = keyname
                    # The value hash is generated from the script
                    # entries, ensuring any changes to this GPO
                    # will cause the scripts to be rewritten.
                    value_hash = self.generate_value_hash(*entries)
                    self.apply(gpo.name, attribute, value_hash,
                               applier_func, keyname, entries)

                # Cleanup any old scripts that are no longer
                # part of the policy
                self.clean(gpo.name, keep=policies.keys())

    def rsop(self, gpo):
        output = {}
        pol_file = 'MACHINE/Registry.pol'
        if gpo.file_sys_path:
            path = os.path.join(gpo.file_sys_path, pol_file)
            pol_conf = self.parse(path)
            if not pol_conf:
                return output
            for e in pol_conf.entries:
                key = e.keyname.split('\\')[-1]
                if key.endswith('Scripts') and e.data.strip():
                    if key not in output.keys():
                        output[key] = []
                    output[key].append(e.data)
        return output

if __name__ == "__main__":
    parser = optparse.OptionParser('gp_scripts_ext.py [options]')
    sambaopts = options.SambaOptions(parser)
    parser.add_option_group(sambaopts)

    parser.add_option('--register',
                      help='Register extension to Samba',
                      action='store_true')
    parser.add_option('--unregister',
                      help='Unregister extension from Samba',
                      action='store_true')

    (opts, args) = parser.parse_args()

    # We're collecting the Samba loadparm simply to
    # find our smb.conf file
    lp = sambaopts.get_loadparm()

    # This is a random unique GUID, which identifies this CSE.
    # Any random GUID will do.
    ext_guid = '{5930022C-94FF-4ED5-A403-CFB4549DB6F0}'
    if opts.register:
        # The extension path is the location of this file. This
        # script should be executed from a permanent location.
        ext_path = os.path.realpath(__file__)
        # The machine and user parameters tell Samba whether to
        # apply this extension to the computer, to individual
        # users, or to both.
        register_gp_extension(ext_guid, 'gp_scripts_ext',
                              ext_path, smb_conf=lp.configfile,
                              machine=True, user=False)
    elif opts.unregister:
        # Remove the extension and do not apply policy.
        unregister_gp_extension(ext_guid)

    # List the currently installed Group Policy Client Side
    # Extensions
    exts = list_gp_extensions(lp.configfile)
    for guid, data in exts.items():
        print(guid)
        for k, v in data.items():
            print('\t%s: %s' % (k, v))
