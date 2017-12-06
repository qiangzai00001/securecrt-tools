# $language = "python"
# $interface = "1.0"

import os
import sys
import logging

# Add script directory to the PYTHONPATH so we can import our modules (only if run from SecureCRT)
if 'crt' in globals():
    script_dir, script_name = os.path.split(crt.ScriptFullName)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
else:
    script_dir, script_name = os.path.split(os.path.realpath(__file__))

# Now we can import our custom modules
from securecrt_tools import script_types
from securecrt_tools.message_box_const import *
from s_update_interface_desc import script_main as update_interface

# Create global logger so we can write debug messages from any function (if debug mode setting is enabled in settings).
logger = logging.getLogger("securecrt")
logger.debug("Starting execution of {}".format(script_name))


# ################################################   SCRIPT LOGIC   ###################################################

def script_main(script):
    """
    | MULTIPLE device script
    | Author: Jamie Caesar
    | Email: jcaesar@presidio.com

    This script will grab the detailed CDP information from a Cisco IOS or NX-OS device and port-channel information and
    generate the commands to update interface descriptions.  The user will be prompted to run in "Check Mode" which will
    write the configuration changes to a file (for verification or later manual application).  If not, then the script
    will push the configuration commands to the device and save the configuration.

    IMPORTANT:  This script imports the script_main() function from the s_update_interface_desc.py to run a majority
    of the script logic.  Much of this script is only handling multiple logins and calling the single-device version of
    this script.

    | Local Settings:
    | "strip_domains" -  A list of domain names that will be stripped away if found in the CDP remote device name.
    | "take_backups" - If True, the script will save a copy of the running config before and after making changes.
    | "rollback_file" - If True, the script will generate a rollback configuration script and save it to a file.

    :param script: A subclass of the sessions.Session object that represents this particular script session (either
                    SecureCRTSession or DirectSession)
    :type script: script_types.Script
    """
    # Create logger instance so we can write debug messages (if debug mode setting is enabled in settings).
    logger = logging.getLogger("securecrt")
    logger.debug("Starting execution of {}".format(script_name))

    # If this is launched on an active tab, disconnect before continuing.
    logger.debug("<M_SCRIPT> Checking if current tab is connected.")
    if script.is_connected():
        logger.debug("<M_SCRIPT> Existing tab connected.  Stopping execution.")
        raise script_types.SecureCRTToolsError("This script must be launched in a not-connected tab.")

    # Load a device list
    device_list = script.import_device_list()
    if not device_list:
        return

    # Ask if this should be a test run (generate configs only) or full run (push updates to devices)
    check_mode_message = "Do you want to run this script in check mode? (Only generate configs)\n" \
                         "\n" \
                         "Yes = Connect to device and write change scripts to a file ONLY\n" \
                         "No = Connect to device and PUSH configuration changes"
    message_box_design = ICON_QUESTION | BUTTON_YESNOCANCEL
    logger.debug("Prompting the user to run in check mode.")
    result = script.message_box(check_mode_message, "Run in Check Mode?", message_box_design)
    if result == IDYES:
        check_mode = True
    elif result == IDNO:
        check_mode = False
    else:
        return

    # Check if we need a jumpbox
    jump_connected = False
    need_jumpbox = script.message_box("Are these devices access through a jump box?", "Jump Box?",
                                      options=ICON_QUESTION|BUTTON_YESNO)
    if need_jumpbox == IDYES:
        jumpbox = script.prompt_window("Enter the Hostname of IP of the jump box.")
        if jumpbox:
            j_username = script.prompt_window("Enter the USERNAME for {}".format(jumpbox))
            if j_username:
                j_password = script.prompt_window("Enter the PASSWORD for {}".format(j_username), hide_input=True)
                if j_password:
                    j_ending = script.prompt_window("Enter the last character of the jumpbox CLI prompt")
                    if j_ending:
                        script.connect_ssh(jumpbox, j_username, j_password, prompt_endings=[j_ending])
                        jump_connected = True

    # Create a filename to keep track of our connection logs, if we have failures.
    connect_log = script.create_output_filename("m_update_interface_desc-LOG", include_hostname=False)

    for device in device_list:
        hostname = device['hostname']
        protocol = device['protocol']
        username = device['username']
        password = device['password']
        enable = device['enable']

        if jump_connected:
            if "ssh" in protocol.lower():
                try:
                    script.ssh_via_jump(hostname, username, password)
                    update_interface(script, prompt_checkmode=False, check_mode=check_mode, enable_pass=enable)
                    script.disconnect_via_jump()
                except (script_types.ConnectError, script_types.InteractionError) as e:
                    error_msg = e.message
                    with open(connect_log, 'a') as logfile:
                        logfile.write("Connect to {} failed: {}\n".format(hostname, error_msg))
            elif protocol.lower() == "telnet":
                try:
                    script.telnet_via_jump(hostname, username, password)
                    update_interface(script, prompt_checkmode=False, check_mode=check_mode, enable_pass=enable)
                    script.disconnect_via_jump()
                except (script_types.ConnectError, script_types.InteractionError) as e:
                    with open(connect_log, 'a') as logfile:
                        logfile.write("Connect to {} failed: {}\n".format(hostname, e.message))
        else:
            try:
                script.connect(hostname, username, password, protocol=protocol)
                update_interface(script, prompt_checkmode=False, check_mode=check_mode, enable_pass=enable)
                script.disconnect()
            except script_types.ConnectError as e:
                with open(connect_log, 'a') as logfile:
                    logfile.write("Connect to {} failed: {}\n".format(hostname, e.message))
            except script_types.InteractionError as e:
                with open(connect_log, 'a') as logfile:
                    logfile.write("Failure on {}: {}\n".format(hostname, e.message))


# ################################################  SCRIPT LAUNCH   ###################################################

# If this script is run from SecureCRT directly, use the SecureCRT specific class
if __name__ == "__builtin__":
    crt_script = script_types.CRTScript(crt)
    script_main(crt_script)

# If the script is being run directly, use the simulation class
elif __name__ == "__main__":
    direct_script = script_types.DirectScript(os.path.realpath(__file__))
    script_main(direct_script)
