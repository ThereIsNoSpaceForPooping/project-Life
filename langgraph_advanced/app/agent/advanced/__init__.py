# -*- coding: utf-8 -*-
"""
Agent 高级功能模块初始化

导出所有高级功能。
"""

from app.agent.advanced.subgraph import research_graph, build_research_subgraph
from app.agent.advanced.interrupt import interrupt_graph, build_interrupt_graph
from app.agent.advanced.parallel import parallel_graph, build_parallel_graph
from app.agent.advanced.mapreduce import mapreduce_graph, build_mapreduce_graph
from app.agent.advanced.dynamic_tools import dynamic_tools_graph, build_dynamic_tools_graph
from app.agent.advanced.time_travel import time_travel_graph, build_time_travel_graph

__all__ = [
    # Subgraph
    "research_graph",
    "build_research_subgraph",
    
    # Interrupt
    "interrupt_graph",
    "build_interrupt_graph",
    
    # Parallel
    "parallel_graph",
    "build_parallel_graph",
    
    # MapReduce
    "mapreduce_graph",
    "build_mapreduce_graph",
    
    # Dynamic Tools
    "dynamic_tools_graph",
    "build_dynamic_tools_graph",
    
    # Time Travel
    "time_travel_graph",
    "build_time_travel_graph"
]
