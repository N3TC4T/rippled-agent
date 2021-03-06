import sys
import os
import subprocess
import stat
from datetime import datetime
import shutil
import glob
import logging

supported_archs = ["amd64"]
BUILD="packaging/build"
PACKAGING="packaging"

ROOT = os.path.abspath(os.path.dirname(__file__))
BINARY="{0}/bin/valmond".format(ROOT)

PACKAGES_PATH=os.path.join(ROOT, PACKAGING, 'distro')
DEBIAN_REPO_PATH="{0}/debian/".format(PACKAGES_PATH)
RPM_REPO_PATH="{0}/centos/".format(PACKAGES_PATH)


def get_version():
    version = run('git describe --always --tags')
    return version


def compile_binary():
    # remove old bin
    try:
        os.remove(BINARY)
    except OSError:
        pass

    version = get_version()
    logging.info("valmond version: {0}".format(version))
    logging.info("Compiling binary")

    build_params = []
    build_params.append("-DCMAKE_BUILD_TYPE=Release")

    command = [
        "sh {0}/binary.sh".format(ROOT),
    ]

    command = command + build_params
    compile_string = " ".join(command)

    start_time = datetime.utcnow()
    run(compile_string, shell=True)
    end_time = datetime.utcnow()
    total_seconds = (end_time - start_time).total_seconds()
    logging.info("Time taken: {0}s".format(total_seconds))


def create_package_fs():
    build_directory = os.path.join(ROOT, BUILD)
    shutil.rmtree(build_directory, ignore_errors=True)
    packaging_directory = os.path.join(ROOT, PACKAGING)

    os.makedirs(build_directory)
    os.makedirs(os.path.join(build_directory, "etc", 'opt', 'valmond'))
    os.makedirs(os.path.join(build_directory, 'opt', 'valmond'))
    os.makedirs(os.path.join(build_directory, "usr", 'bin'))

    st = os.stat(BINARY)
    os.chmod(BINARY, st.st_mode | stat.S_IEXEC)

    shutil.copyfile(BINARY, os.path.join(build_directory, 'opt', 'valmond', 'valmond'))
    shutil.copyfile(BINARY, os.path.join(build_directory, 'usr', 'bin', 'valmond'))


    os.makedirs(os.path.join(build_directory, "var", 'log', 'valmond'))
    # os.chmod(os.path.join(build_directory, "var", 'log', 'valmond'), 755)


    # # /var/run permissions for RPM distros
    os.makedirs(os.path.join(build_directory, "usr", 'lib', 'tmpfiles.d'))
    shutil.copyfile(
        os.path.join(packaging_directory, 'tmpfilesd_valmond.conf'),
        os.path.join(build_directory, 'usr', 'lib', 'tmpfiles.d', 'valmond.conf')
    )


    os.makedirs(os.path.join(build_directory, "opt", 'valmond', 'scripts'))
    shutil.copyfile(
        os.path.join(packaging_directory, 'init.sh'),
        os.path.join(build_directory, 'opt', 'valmond', 'scripts', 'init.sh')
    )

    shutil.copyfile(
        os.path.join(packaging_directory, 'valmond.service'),
        os.path.join(build_directory, 'opt', 'valmond', 'scripts', 'valmond.service')
    )

    shutil.copyfile(
        os.path.join(packaging_directory, 'valmond.cfg'),
        os.path.join(build_directory, 'etc', 'opt', 'valmond', 'valmond.cfg')
    )


def fpm_build(arch=None, output=None):
    logging.info("Building package for: {0} / {1}".format(arch, output))
    build_directory = os.path.join(ROOT, BUILD)
    packaging_directory = os.path.join(ROOT, PACKAGING)

    command = [
        'fpm',
        '--epoch 1',
        '--force',
        '--input-type dir',
        '--output-type {0}'.format(output),
        '--chdir {0}'.format(build_directory),
        '--maintainer "XRPL Labs <packages@xrpl-labs.com>"',
        '--url "https://xrpl-labs.com/"',
        '--description "XRPL Validator monitoring agent"',
        '--version {0}'.format(get_version()),
        '--conflicts "valmond < {0}"'.format(get_version()),
        '--vendor XRPL-Labs',
        '--name valmond',
        '--depends "curl"',
        '--architecture "{0}"'.format(arch),
        '--post-install {0}'.format(os.path.join(packaging_directory, 'postinst.sh')),
        '--post-uninstall {0}'.format(os.path.join(packaging_directory, 'postrm.sh')),
        '--pre-uninstall {0}'.format(os.path.join(packaging_directory, 'prerm.sh')),
    ]

    if output == 'deb':
        command.extend(['--depends "libcurl3 | libcurl4"'])

    command_string = " ".join(command)
    run(command_string, shell=True)


def run(command, allow_failure=False, shell=False, printOutput=False):
    """
    Run shell command (convenience wrapper around subprocess).
    If printOutput is True then the output is sent to STDOUT and not returned
    """
    out = None
    logging.debug("{}".format(command))
    try:
        cmd = command
        if not shell:
            cmd = command.split()

        stdout = subprocess.PIPE
        stderr = subprocess.STDOUT
        if printOutput:
            stdout = None

        p = subprocess.Popen(cmd, shell=shell, stdout=stdout, stderr=stderr)
        out, _ = p.communicate()
        if out is not None:
            out = out.decode('utf-8').strip()
        if p.returncode != 0:
            if allow_failure:
                logging.warn(u"Command '{}' failed with error: {}".format(command, out))
                return None
            else:
                logging.error(u"Command '{}' failed with error: {}".format(command, out))
                sys.exit(1)
    except OSError as e:
        if allow_failure:
            logging.warn("Command '{}' failed with error: {}".format(command, e))
            return out
        else:
            logging.error("Command '{}' failed with error: {}".format(command, e))
            sys.exit(1)
    else:
        return out

def update_repositories():
    try:
        os.makedirs(PACKAGES_PATH)
        os.makedirs(DEBIAN_REPO_PATH)
        os.makedirs(RPM_REPO_PATH)
    except OSError:
        pass

    for file in glob.glob("*.deb"):
        logging.info("Copying {0} to {1}".format(file, DEBIAN_REPO_PATH))
        shutil.copy(file, DEBIAN_REPO_PATH)

    for file in glob.glob("*.rpm"):
        logging.info("Copying {0} to {1}".format(file, RPM_REPO_PATH))
        shutil.copy(file, RPM_REPO_PATH)


def cleanup():
    for file in glob.glob("*.rpm"):
        logging.info("Cleaning up {0}".format(file))
        os.remove(file)

    for file in glob.glob("*.deb"):
        logging.info("Cleaning up {0}".format(file))
        os.remove(file)

if __name__ == '__main__':
    LOG_LEVEL = logging.INFO
    if '--debug' in sys.argv[1:]:
        LOG_LEVEL = logging.DEBUG
    log_format = '[%(levelname)s] %(funcName)s: %(message)s'
    logging.basicConfig(level=LOG_LEVEL, format=log_format)

    compile_binary()
    create_package_fs()

    output = ["rpm", 'deb']

    if(len(sys.argv) > 1):
        output = [sys.argv[1]]

    for arch in supported_archs:
        for ext in output:
            fpm_build(arch=arch, output=ext)

    update_repositories()
    cleanup()

