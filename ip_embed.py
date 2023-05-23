from itertools import product
from dwave.embedding import pegasus
import dwave.inspector
import minorminer
import dwave_networkx as dnx
import networkx as nx

import gurobipy as gb
from gurobipy import GRB

def define_decision_variables(target, graph, model):

    var_dict = {}
    for v in target.nodes:
        for w in graph.nodes:
            var_dict[(v,w)] = model.addVar(vtype=GRB.BINARY, name=f'x_{v},{w}')
    return var_dict


def define_gamma_variables(chains, j, k, var_dict, model):
    ls = []
    for c in chains:
        if len(c) > 0:
            ls.append(model.addVar(vtype=GRB.BINARY, name=f'gamma_{c}_{j}'))

            s = 1
            for i in range(1, len(c)-1):
                s *= var_dict[c[i],j]
            model.addConstr( ls[-1] == s )

    return ls

def define_delta_p_variable(x1,x2,y1,y2,var_dict ,model):
    delta = model.addVar(vtype=GRB.BINARY, name=f'delta_{x1}{x2}{y1}{y2}')
    model.addConstr(delta == var_dict[(x1,y1)] * var_dict[(x2,y2)])
    return delta

def define_delta_o_variable(x1,x2,y1,y2,var_dict ,model):
    delta = model.addVar(vtype=GRB.BINARY, name=f'delta_{x1}{x2}{y1}{y2}')
    model.addConstr(delta == var_dict[(x1,y2)] * var_dict[(x2,y1)])
    return delta

def add_size_constraint(var_dict, model, max, min):
    model.addConstr(sum(var_dict.values()) <= max, name='size_constraint')
    model.addConstr(sum(var_dict.values()) >= min, name='size_constraint')

def add_wd_constraint(target, graph, var_dict, model):
    for n in target.nodes:
        tmp = 0
        for k in graph.nodes:
            tmp += var_dict[(n,k)]
        
        model.addConstr(tmp <= 1, name=f'well_defined_constraint_{n}')

def add_fs_constraint(target, graph, var_dict, model, k):
    for n in graph.nodes:
        tmp = 0
        for k in target.nodes:
            tmp += var_dict[k,n]
        
        model.addConstr(tmp <= k, name=f'fiber_size_max_constraint_{n}')
        model.addConstr(tmp >= 1, name=f'fiber_size_min_constraint_{n}')

def add_fs_refinement(target, graph, var_dict, model, k):
    ls = set()
    t_nodes = set(target.nodes)
    for x1 in t_nodes:
        ls.add(x1)
        for x2 in t_nodes-ls:
            chains = list(nx.all_simple_paths(target, x1, x2, k))
            if len(chains) == 0:
                for j in graph.nodes:
                    tmp = var_dict[x1,j] + var_dict[x2,j]
                    model.addConstr(tmp <= 1, name=f'fs_ref_{j}_{x1}_{x2}')


def add_pullback_constraint(target, graph, model, var_dict):
    for ey in graph.edges:
        s = 0
        for ex in target.edges:
            d_p = define_delta_p_variable(ex[0], ex[1], ey[0], ey[1], var_dict, model)
            d_o = define_delta_o_variable(ex[0], ex[1], ey[0], ey[1], var_dict, model)

            s += d_p+d_o
            model.addConstr(s <= 1, name=f'pullback_ds_{ey}_{ex}')
        model.addConstr(1 <= s, name=f'pullback_{ey}')


def add_fiber_constraint(graph, target, k, var_dict, model):
    for j in graph.nodes:
        ls = set()
        t_nodes = set(target.nodes)
        for x1 in t_nodes:
            ls.add(x1)
            for x2 in t_nodes-ls:

                chains = list(nx.all_simple_paths(target, x1, x2, k))
                if len(chains) > 0:
                    gammas = define_gamma_variables(chains, j, k, var_dict, model)

                    model.addConstr( var_dict[(x1,j)] + var_dict[(x2,j)] + sum(gammas) - 1 <= 2)