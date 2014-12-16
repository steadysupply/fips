"""project related functions"""

import os
import shutil
import subprocess

from mod import log, util, config
from mod.tools import git, cmake, make, ninja, xcodebuild

#-------------------------------------------------------------------------------
def is_valid_project_dir(proj_dir) :
    """test if the provided directory is a valid fips project (has a
    fips.yml and a fips file)

    :param proj_dir:    absolute project directory to check
    :returns:           True if a valid fips project
    """
    if os.path.isdir(proj_dir) :
        if not os.path.isfile(proj_dir + '/fips') :
            log.error("no file 'fips' in project dir '{}'".format(proj_dir), False)
            return False
        if not os.path.isfile(proj_dir + '/fips.yml') :
            log.error("no file 'fips.yml' in project dir '{}'".format(proj_dir), False)
            return False
        return True
    return False

#-------------------------------------------------------------------------------
def is_valid_project(fips_dir, name) :
    """test if a named project directory exists in the fips workspace and
    check whether a fips bootstrap script and fips.yml file exists
    
    :param fips_dir:    absolute path of fips
    :param name:        project/directory name
    :returns:           True if this is a valid fips project
    """
    proj_dir = util.get_project_dir(fips_dir, name)
    return is_valid_project_dir(proj_dir)

#-------------------------------------------------------------------------------
def init(fips_dir, proj_name) :
    """initialize an existing project directory as a fips directory by
    copying a fips python script and fips.yml file to it. the directory
    must exist in the same directory as the fips directory.

    :param fips_dir:    absolute path to fips
    :param proj_name:   project directory name (dir must exist)
    :returns:           True if the project was successfully initialized
    """
    ws_dir = util.get_workspace_dir(fips_dir)
    proj_dir = util.get_project_dir(fips_dir, proj_name)
    if os.path.isdir(proj_dir) :
        src = fips_dir + '/templates/fips'
        dst = proj_dir + '/fips'
        if not os.path.isfile(dst) :
            shutil.copy(src, dst)
            os.chmod(dst, 0o744)
            log.info("copied '{}' to '{}'".format(src, dst))
        else :
            log.warn("file '{}' already exists".format(dst))
        src = fips_dir + '/templates/fips.yml'
        dst = proj_dir + '/fips.yml'
        if not os.path.isfile(dst) :
            shutil.copy(src, dst)
            log.info("copied '{}' to '{}'".format(src, dst))
        else :
            log.warn("file '{}' already exists".format(dst))
        log.info("project dir initialized, please edit '{}' next".format(dst))
        return True
    else :
        log.error("project dir '{}' does not exist".format(proj_dir))
        return False

#-------------------------------------------------------------------------------
def clone(fips_dir, url) :
    """clone an existing fips project with git, do NOT fetch dependencies

    :param fips_dir:    absolute path to fips
    :param url:         git url to clone from
    :return:            True if project was successfully cloned
    """
    ws_dir = util.get_workspace_dir(fips_dir)
    proj_name = util.get_project_name_from_url(url)
    proj_dir = util.get_project_dir(fips_dir, proj_name)
    if not os.path.isdir(proj_dir) :
        if git.clone(url, proj_name, ws_dir) :
            return True
        else :
            log.error("failed to 'git clone {}' into '{}'".format(url, proj_dir))
            return False
    else :
        log.error("project dir '{}' already exists".format(proj_dir))
        return False

#-------------------------------------------------------------------------------
def gen_project(fips_dir, proj_dir, build_dir, cfg) :
    """private: generate build files for one config"""
    toolchain_path = config.get_toolchain_for_platform(fips_dir, cfg['platform'])
    return cmake.run_gen(cfg, proj_dir, build_dir, toolchain_path)

#-------------------------------------------------------------------------------
def gen(fips_dir, proj_dir, cfg_name, proj_name) :
    """generate build files with cmake

    :param fips_dir:    absolute path to fips
    :param proj_dir:    absolute path to project
    :param cfg_name:    config name or pattern (e.g. osx-make-debug)
    :param proj_name:   project name (or None to use current project path)
    :returns:           True if successful
    """

    # if a project name is given, build a project dir from it
    if proj_name :
        proj_dir = util.get_project_dir(fips_dir, proj_name)
    else :
        proj_name = util.get_project_name_from_dir(proj_dir)

    # check if proj_dir is a valid fips project
    if not is_valid_project_dir(proj_dir) :
        log.error("'{}' is not a valid fips project".format(proj_dir))
    
    # load the config(s)
    configs = config.load(cfg_name, [fips_dir])
    num_valid_configs = 0
    for cfg in configs :
        # check if config is valid
        if config.check_config_valid(cfg) :
            log.colored(log.YELLOW, "=== generating: {}".format(cfg['name']))

            # get build-dir and make sure it exists
            build_dir = util.get_build_dir(fips_dir, proj_name, cfg)
            if not os.path.isdir(build_dir) :
                os.makedirs(build_dir)
            if gen_project(fips_dir, proj_dir, build_dir, cfg) :
                num_valid_configs += 1
            else :
                log.error("failed to generate build files for config '{}'".format(cfg['name']), False)
        else :
            log.error("'{}' is not a valid config".format(cfg['name']), False)

    if num_valid_configs != len(configs) :
        log.error('{} out of {} configs failed!'.format(len(configs) - num_valid_configs, len(configs)))
        return False      
    else :
        log.colored(log.GREEN, '{} configs generated'.format(num_valid_configs))
        return True

#-------------------------------------------------------------------------------
def build(fips_dir, proj_dir, cfg_name, proj_name) :
    """perform a build of config(s) in project

    :param fips_dir:    absolute path of fips
    :param proj_dir:    absolute path of project dir
    :param cfg_name:    config name or pattern
    :param proj_name:   project name (override project dir) or None
    :returns:           True if build was successful
    """

    # if a project name is given, build a project dir from it
    if proj_name :
        proj_dir = util.get_project_dir(fips_dir, proj_name)
    else :
        proj_name = util.get_project_name_from_dir(proj_dir)

    # check if proj_dir is a valid fips project
    if not is_valid_project_dir(proj_dir) :
        log.error("'{}' is not a valid fips project".format(proj_dir))
    
    # load the config(s)
    configs = config.load(cfg_name, [fips_dir])
    num_valid_configs = 0
    for cfg in configs :
        # check if config is valid
        if config.check_config_valid(cfg) :
            log.colored(log.YELLOW, "=== building: {}".format(cfg['name']))

            # generate build files on demand
            build_dir = util.get_build_dir(fips_dir, proj_name, cfg)
            if not os.path.isdir(build_dir) :
                log.colored(log.YELLOW, "=== generating: {}".format(cfg['name']))
                os.makedirs(build_dir)
                if not gen_project(fips_dir, proj_dir, build_dir, cfg) :
                    log.error("Failed to generate '{}' of project '{}'".format(cfg['name'], proj_name))

            # select and run build tool
            # FIXME: make number of jobs configurable
            # FIXME: make target configurable?
            target = None
            num_jobs = 3
            result = False
            if cfg['build_tool'] == make.name :
                result = make.run_build(target, build_dir, num_jobs)
            elif cfg['build_tool'] == ninja.name :
                result = ninja.run_build(target, build_dir, num_jobs)
            elif cfg['build_tool'] == xcodebuild.name :
                result = xcodebuild.run_build(target, cfg['build_type'], build_dir, num_jobs)
            else :
                result = cmake.run_build(target, cfg['build_type'], build_dir)
            
            if not result :
                log.error("Failed to build config '{}' of project '{}'".format(cfg['name'], proj_name))

    log.colored(log.GREEN, "Successfully built {} configs in project '{}'".format(len(configs), proj_name))
    return True

#-------------------------------------------------------------------------------
def run(fips_dir, proj_dir, cfg_name, proj_name, target_name) :
    """run a build target executable

    :param fips_dir:    absolute path of fips
    :param proj_dir:    absolute path of project dir
    :param cfg_name:    config name or pattern
    :param proj_name:   project name (override project dir) or None
    :param target_name: the target name
    :returns:           True if build was successful
    """

    # if a project name is given, build a project dir from it
    if proj_name :
        proj_dir = util.get_project_dir(fips_dir, proj_name)
    else :
        proj_name = util.get_project_name_from_dir(proj_dir)

    # check if proj_dir is a valid fips project
    if not is_valid_project_dir(proj_dir) :
        log.error("'{}' is not a valid fips project".format(proj_dir))
    
    # load the config(s)
    configs = config.load(cfg_name, [fips_dir])
    num_valid_configs = 0
    for cfg in configs :
        log.colored(log.YELLOW, "=== run '{}' (config: {}, project: {}):".format(target_name, cfg['name'], proj_name))

        # find deploy dir where executables live
        deploy_dir = util.get_deploy_dir(fips_dir, proj_name, cfg)

        # special case: Mac app
        if os.path.isdir('{}/{}.app'.format(deploy_dir, target_name)) :
            cmdLine = ['open', '{}/{}.app'.format(deploy_dir, target_name)]
        else :
            cmdLine = [ '{}/{}'.format(deploy_dir, target_name) ]
        try:
            subprocess.call(args=cmdLine, cwd=deploy_dir)
        except OSError, e:
            log.error("Failed to execute '{}' with '{}'".format(target_name, e.strerror))

