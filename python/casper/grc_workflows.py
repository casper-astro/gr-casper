"""Workflow for generating RFNoC bitfiles from GRC.

Copyright 2024 Ettus Research, an NI Brand

This file is part of GNU Radio

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import os
import subprocess
import tempfile
import json
from pathlib import Path

from gnuradio.grc.core import Messages
from gnuradio.grc.core.generator.FlowGraphProxy import FlowGraphProxy
from gnuradio.grc.workflows import GeneratorBase
from gnuradio.grc.workflows.common import add_xterm_to_run_command

class FlowgraphInfo(object):
    unnecessary_keys = ['alias', 'affinity', 'minoutbuf', 'maxoutbuf', 'comment']
    def __init__(self, flowgraph, input_file):
        self.flow_graph = flowgraph
        self.input_file = input_file
        self.builddir = self.input_file.split('.')[0]
        os.makedirs(self.builddir, exist_ok=True)
        self.flowgraph_name = input_file.split('/')[-1].split('.')[0]
        self.flowgraph_info = {}
        self.flowgraph_info['project'] = {}
        self.flowgraph_info['project']['tag'] = 'proj'
        self.flowgraph_info['project']['filename'] = self.input_file
        self.flowgraph_info['xps_blocks'] = []
        self.flowgraph_info['dsp_blocks'] = []
        self.flowgraph_info['link_info'] = []

    def _search_block_tag_by_name(self, name):
        for b in self.flowgraph_info['xps_blocks']:
            if b['name'] == name:
                return 'xps'
        for b in self.flowgraph_info['dsp_blocks']:
            if b['name'] == name:
                return 'dsp'
        return None
    
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
                    block_info['tag'] = '%s:%s'%(tag, b.key)
                else:
                    block_info[param_id] = str(param.value)
                block_info['fullpath'] = '%s/%s'%(self.flowgraph_name, block_info['name'] )
            if tag == 'xps':
                self.flowgraph_info['xps_blocks'].append(block_info)
            elif tag == 'dsp':
                self.flowgraph_info['dsp_blocks'].append(block_info)


    def get_block_connections(self):
        for c in self.flow_graph.get_enabled_connections():
            src_blk_name = c.source_block.name
            src_blk_tag = self._search_block_tag_by_name(src_blk_name)
            src_port_name = '%s_%s_%s'%(self.flowgraph_name ,src_blk_name, c.source_port.name)
            src_port_id = int(c.source_port.key)
            # TODO: get the port width from the port
            src_port_width = 32
            dst_blk_name = c.sink_block.name
            dst_blk_tag = self._search_block_tag_by_name(dst_blk_name)
            dst_port_name = '%s_%s_%s'%(self.flowgraph_name ,dst_blk_name, c.sink_port.name)
            dst_port_id = int(c.sink_port.key)
            # TODO: get the port width from the port
            dst_port_width = 32
            link_info = {}
            link_info['src_blk_name'] = src_blk_name
            link_info['src_port_name'] = src_port_name
            link_info['src_port_width'] = src_port_width
            link_info['src_port_id'] = src_port_id + 1
            link_info['dst_blk_name'] = dst_blk_name
            link_info['dst_port_name'] = dst_port_name
            link_info['dst_port_width'] = dst_port_width
            link_info['dst_port_id'] = dst_port_id + 1
            link_info['link_type'] = '%s_%s'%(src_blk_tag, dst_blk_tag)
            self.flowgraph_info['link_info'].append(link_info)
    
    def gen_jasper_json(self):
        filename = '%s/jasper.json'%self.builddir
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.flowgraph_info, f, ensure_ascii=False, indent=4)


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
        self.fginfo = FlowgraphInfo(self.flow_graph, self.input_file)
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
        # for b in self.flow_graph.get_enabled_blocks():
        #     print(b.key)
        #     for param_id, param in b.params.items():
        #         print('param_id:', param_id)
        #         print('param value:', param.value)
        #     print(type(b))
        # for c in self.flow_graph.get_enabled_connections():
        #     print(c)
        #     print('src_blk:', c.source_block)
        #     print('src_blk.key:', c.source_block.key)
        #     print('src_blk.name:', c.source_block.name)
        #     print('src_port:', c.source_port)
        #     print('src_port.key:', c.source_port.key)
        #     print('src_port.name:', c.source_port.name)
        #     print(c.sink_block)
        #     print(c.sink_port)
        # image_builder_cmd = "cd /data/wei; ls"
        # proc_info = subprocess.run(
        #     image_builder_cmd,
        #     stdout=subprocess.PIPE,
        #     stderr=subprocess.STDOUT,
        #     universal_newlines=True,
        #     shell=True
        # )
        # os.system(image_builder_cmd)
        self.fginfo.get_block_parameters()
        self.fginfo.get_block_connections()
        self.fginfo.gen_jasper_json()
        scilab_library_path = os.getenv('MLIB_DEVEL_PATH')+'/scilab_library';
        modelpath = self.input_file
        frontend_cmd = scilab_library_path+'/jasper_frontend.py' + ' ' + '-m ' + modelpath
        frontend_cmd = '/home/wei/miniconda3/envs/m2021a/bin/python %s'%(frontend_cmd)
        print('frontend_cmd: ', frontend_cmd)
        os.system(frontend_cmd)
        cmd = {}
        cmd['dsp'] = '/home/wei/miniconda3/envs/m2021a/bin/python /home/wei/scilab_demo/mlib_devel/scilab_library/gen_dsp_ip.py -m %s'%self.input_file
        cmd['full'] = '/home/wei/miniconda3/envs/m2021a/bin/python /home/wei/scilab_demo/mlib_devel/jasper_library/exec_flow.py -m %s --middleware --backend --software --vitis'%self.input_file
        os.system(cmd['dsp'])
        os.system(cmd['full'])


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
