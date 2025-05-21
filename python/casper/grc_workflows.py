"""Workflow for generating RFNoC bitfiles from GRC.

Copyright 2024 Ettus Research, an NI Brand

This file is part of GNU Radio

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from gnuradio.grc.core import Messages
from gnuradio.grc.core.generator.FlowGraphProxy import FlowGraphProxy
from gnuradio.grc.workflows import GeneratorBase
from gnuradio.grc.workflows.common import add_xterm_to_run_command

class FlowgraphInfo(object):
    unnecessary_keys = ['alias', 'affinity', 'minoutbuf', 'maxoutbuf']
    def __init__(self, flowgraph, input_file):
        self.flowgraph = flowgraph
        self.input_file = input_file
        self.flowgraph_name = input_file.split('/')[-1].split('.')[0]
        self.flowgraph_info = {}
        self.flowgraph_info['project'] = {}
        self.flowgraph_info['project']['tag'] = 'proj'
        self.flowgraph_info['project']['filename'] = self.input_file
        self.flowgraph_info['xps_blocks'] = []
        self.flowgraph_info['dsp_blocks'] = []

    def _get_block_tag(self, b):
        for param_id, param in b.params.items():
            if param_id == 'tag':
                return param.value
        return None
    
    def get_block_parameters(self):
        for b in self.flow_graph.get_enabled_blocks():
            # we don't need to get the parameters from 
            # the options and variable blocks.
            if b.key == 'options' or b.key == 'variable':
                continue
            tag = self._get_block_tag(b)
            block_info = {}
            for param_id, param in b.params.items():
                print('param_id:', param_id)
                print('param value:', param.value)
                if param_id in FlowgraphInfo.unnecessary_keys:
                    continue
                # rename 'id 'to 'name', as we need 'name' in casper toolflow
                elif param_id == 'id':
                    block_info['name'] = str(param.value)
                elif param_id == 'tag':
                    block_info['tag'] = '%s:%s'%(tag, str(param.value))
                else:
                    block_info[param_id] = str(param.value)
                block_info['fullpath'] = '%s/%s'%(self.flowgraph_name, block_info['name'] )
            if tag == 'xps':
                self.flowgraph_info['xps_block'].append(block_info)
            elif tag == 'dsp':
                self.flowgraph_info['dsp_block'].append(block_info)


    def get_block_connections(self):
        pass

    def search_block_tag(self):
        pass
    
    def gen_jasper_json(self):
        pass

def _get_output_path(fg, output_dir):
    """Generate the output path for the image core artefacts.

    - If the user has defined a directory, check it's writable and use it.
    - Otherwise, use the output directory.
    - If the output directory is not writable, use the system temp directory.
    """
    image_core_name = fg.get_option("id")
    if fg.get_option("build_dir"):
        if not os.access(fg.get_option("build_dir"), os.W_OK):
            raise ValueError(
                f"Build directory {fg.get_option('build_dir')} is not writable")
        return os.normpath(os.path.abspath(fg.get_option('build_dir')))
    build_dir_name = "build-" + image_core_name
    if not os.access(output_dir, os.W_OK):
        return os.path.join(tempfile.gettempdir(), build_dir_name)
    return os.path.join(output_dir, build_dir_name)


# def generate_build_command(input_file, build_dir, flow_graph):
#     """Generate the build command for the RFNoC image."""
#     args = ['rfnoc_image_builder', ]
#     if flow_graph.get_option('fpga_dir'):
#         args.extend(['--fpga-dir', flow_graph.get_option('fpga_dir')])
#     build_dir = os.path.normpath(os.path.abspath(build_dir))
#     build_output_dir = flow_graph.get_option('build_output') \
#         if flow_graph.get_option('build_output') \
#         else str(Path(input_file).parent)
#     build_ip_dir = flow_graph.get_option('build_ip') \
#         if flow_graph.get_option('build_ip') \
#         else os.path.join(build_dir, 'build-ip')
#     include_dirs = [d.strip() for d in flow_graph.get_option('include_dirs').split(os.pathsep) if d.strip()]
#     for include_dir in include_dirs:
#         args.extend(['-I', include_dir])
#     args.extend([
#         "--build-dir", build_dir,
#         "--build-output-dir", build_output_dir,
#         "--build-ip-dir", build_ip_dir])
#     if flow_graph.get_option('jobs'):
#         args.extend(['--jobs', str(flow_graph.get_option('jobs'))])
#     else:
#         args.extend(['--jobs', str(os.cpu_count)])
#     if not flow_graph.get_option('include_hash'):
#         args.append('--no-hash')
#     if not flow_graph.get_option('include_date'):
#         args.append('--no-date')
#     if flow_graph.get_option('vivado_path'):
#         args.extend(['--vivado-path', flow_graph.get_option('vivado_path')])
#     if flow_graph.get_option('ignore_warnings'):
#         args.append('--ignore-warnings')
#     if flow_graph.get_option('reuse'):
#         args.append('--reuse')
#     args.extend(['--grc-config', input_file])
#     return args


class CASPERImageGenerator(GeneratorBase):
    """Generator class for RFNoC bitfiles from GRC."""

    def __init__(self, flow_graph, output_dir):
        """Initialize the RfnocImageGenerator object.

        Args:
            flow_graph: The flow graph to generate the RFNoC image for.
            output_dir: The directory to output the generated image to.
        """
        self.flow_graph = FlowGraphProxy(flow_graph)
        # file_path is the build artifact dir. We call it file_path because GRC
        # expects this attribute and uses it to generate a message.
        self.file_path = _get_output_path(flow_graph, output_dir)
        self.input_file = flow_graph.grc_file_path
        self.log = logging.getLogger(self.__class__.__name__)
        self.xterm = self.flow_graph.parent_platform.config.xterm_executable
        print('file_path', self.file_path)
        print('input_file', self.input_file)

    def write(self, called_from_exec=False):
        """Generate the RFNoC image."""
        """
        if called_from_exec:
            self.log.debug("Skipping implied image core generation")
            return
        image_builder_cmd = generate_build_command(
            self.input_file, self.file_path, self.flow_graph) + ['--generate-only']
        self.log.debug("Launching image builder: %s", image_builder_cmd)
        proc_info = subprocess.run(
            image_builder_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        # FIXME error handling
        if proc_info.stdout:
            Messages.send_verbose_exec(proc_info.stdout)
        """
        print('current path:', os.getcwd())
        for b in self.flow_graph.get_enabled_blocks():
            print(b.key)
            for param_id, param in b.params.items():
                print('param_id:', param_id)
                print('param value:', param.value)
            print(type(b))
        for c in self.flow_graph.get_enabled_connections():
            print(c)
            print(c.source_block)
            print(c.source_port)
            print(c.sink_block)
            print(c.sink_port)
        image_builder_cmd = "cd /data/wei; ls"
        # proc_info = subprocess.run(
        #     image_builder_cmd,
        #     stdout=subprocess.PIPE,
        #     stderr=subprocess.STDOUT,
        #     universal_newlines=True,
        #     shell=True
        # )
        os.system(image_builder_cmd)
        print('hello')
        print('in write')


    def get_exec_args(self):
        """Return a process object that executes the RFNoC image generation."""
        """
        image_builder_cmd = generate_build_command(
            self.input_file, self.file_path, self.flow_graph)
        image_builder_cmd = add_xterm_to_run_command(image_builder_cmd, self.xterm)
        return dict(
            args=image_builder_cmd,
            shell=False,
        )
        """
        print('in get_exec_args')
