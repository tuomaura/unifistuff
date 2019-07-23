# Copyright 2019 Tuomas Aura. See LICENSE.txt for the license.

import json

def make_table_name(network_name, direction, special=None):
    if special:
        return '_'.join((network_name, direction, special, 'v6'))
    else: 
        return '_'.join((network_name, direction, 'v6'))

def make_network_description(net):
    desc = net['name']
    notes = []
    if net['vlan']:
        notes.append('vlan ' + str(net['vlan']))
    if net['note']:
        notes.append(net['note'])
    if notes:
        desc = desc + ' (' + ', '.join(notes) + ')'
    return desc

def default_mod_tables(networks, default_action, log_default):
    tables = { 'ipv6-modify': {} }
    for net in networks:
        desc = make_network_description(net)
        in_table_name = make_table_name(net['name'], 'IN', 'MOD')
        tables['ipv6-modify'][in_table_name] = {
            'description': f'Mark incoming packets from {desc}',
            'rule': {
                2000: {
                    'action': 'modify',
                    'modify': {
                        'mark': str(net['mark'])
                    },
                    'log': 'disable'
                }
            }
        }
        out_table_name = make_table_name(net['name'], 'OUT', 'MOD')
        tables['ipv6-modify'][out_table_name] = {
            'description': f'Filter outgoing packets to {desc}',
            'rule': {
                2000: {
                    'action': 'accept',
                    'state': {
                        'established': 'enable',
                        'related': 'enable'
                    },
                    'log': 'disable'
                },
                2001: {
                    'action': 'accept',
                    'protocol': 'ipv6-icmp',
                    'icmpv6': {
                        'type': '134'
                    }
                },
                2002: {
                    'action': 'accept',
                    'protocol': 'ipv6-icmp',
                    'icmpv6': {
                        'type': '135'
                    }
                },
                2003: {
                    'action': 'accept',
                    'protocol': 'ipv6-icmp',
                    'icmpv6': {
                        'type': '136'
                    }
                },
                2999: {
                    'description': 'default action',
                    'action': default_action,
                    'log': 'enable' if log_default else 'disable'
                }
            }
        }
    return tables

def specific_exception(tables, src_mark, dst_name, action, log, note):
    out_table_name = make_table_name(dst_name, 'OUT', 'MOD')
    rules = tables['ipv6-modify'][out_table_name]['rule']
    number = 2000
    while number in rules:
        number = number + 1
    rules[number] = {
        'action': action,
        'mark': str(src_mark),
        'log': 'enable' if log else 'disable'
    }
    if note:
        rules[number]['description'] = note

def src_wildcard_exception(tables, dst_name, action, log, note):
    out_table_name = make_table_name(dst_name, 'OUT', 'MOD')
    rules = tables['ipv6-modify'][out_table_name]['rule']
    number = 2000
    while number in rules:
        number = number + 1
    rules[number] = {
        'action': action,
        'log': 'enable' if log else 'disable'
    }
    del rules[2999]
    if note:
        desc = 'Override default action: ' + note
    else:
        desc = 'Override default action'
    rules[number]['description'] = desc

def dst_wildcard_exception(tables, src_mark, networks, action, log, note):
    for net in networks:
        if net['mark'] != src_mark:
            specific_exception(tables, src_mark, net['name'], action, log, note)

def attach_to_interfaces(networks):
    interfaces = { 'ethernet': {} }
    for net in networks:
        in_table_name = make_table_name(net['name'], 'IN', 'MOD')
        out_table_name = make_table_name(net['name'], 'OUT', 'MOD')
        if net['if'] not in interfaces['ethernet']:
            interfaces['ethernet'][net['if']] = {}       
        firewall = {
            'firewall': {
                'in': {
                    'ipv6-modify': in_table_name
                },
                'out': { 
                    'ipv6-modify': out_table_name
                }
            }
        }
        if net['vlan']:
            if 'vif' not in interfaces['ethernet'][net['if']]:
                interfaces['ethernet'][net['if']]['vif'] = {}
            interfaces['ethernet'][net['if']]['vif'][net['vlan']] = firewall
        else:
            interfaces['ethernet'][net['if']] = firewall
    return interfaces

def make_firewall(networks, default_action, exceptions, log_default):
    if default_action not in ('drop', 'accept'):
        raise ValueError(f'Invalid default action: {default_action}. Use "drop" or "accept".')
    non_default_action = 'drop' if default_action == 'accept' else 'accept'
    for net in networks:
        fields = ('name', 'if', 'vlan', 'mark', 'note')
        for f in fields:
            if f not in net:
                raise ValueError(f'Must specify field {f} for all networks.') 
        if not isinstance(net['vlan'], (int, type(None))):
            raise ValueError(f'Invalid VLAN: {net["vlan"]}. Should be integer or None.')     
        if not isinstance(net['mark'], (int, type(None))):
            raise ValueError(f'Invalid VLAN: {net["mark"]}. Should be integer or None.')     
    network_names = [ net['name'] for net in networks ] 
    for name in network_names:
        if network_names.count(name) > 1:
            raise ValueError(f'Network name {name} repeated.')        
    names_to_marks = { net['name']: net['mark'] for net in networks }
    for ex in exceptions:
        fields = ('src', 'dst', 'log', 'note')
        for f in fields:
            if f not in ex:
                raise ValueError(f'Must specify field {f} for all exceptions.') 
    for ex in exceptions:
        if ex['src'] == '*' and ex['dst'] == '*':
            raise ValueError('Exception cannot have wildcard * as both source and destination.')
        for name in (ex['src'], ex['dst']):
            if name != '*' and name not in network_names:
                raise ValueError(f'{name} in exceptions but not in network names.')

    tables = default_mod_tables(networks, default_action, log_default)
    for ex in exceptions:
        if ex['src'] == '*':
            src_wildcard_exception(tables, ex['dst'], non_default_action, ex['log'], ex['note'])
        else:
            src_mark = names_to_marks[ex['src']]
            if ex['dst'] == '*':
                dst_wildcard_exception(tables, src_mark, networks, non_default_action, ex['log'], ex['note'])
            else:
                specific_exception(tables, src_mark, ex['dst'], non_default_action, ex['log'], ex['note'])
    interfaces = attach_to_interfaces(networks)
    return { 'firewall': tables, 'interfaces': interfaces }


#==========================================================================
# Example home network specification

networks = [
    { 'name': 'WAN',      'if':'eth0', 'vlan': None, 'mark': 1000, 'note': None },
    { 'name': 'LAN',      'if':'eth1', 'vlan': None, 'mark': 1001, 'note': 'infra'  },
    { 'name': 'VLAN1002', 'if':'eth1', 'vlan': 1002, 'mark': 1002, 'note': 'users'  },
    { 'name': 'VLAN1004', 'if':'eth1', 'vlan': 1004, 'mark': 1004, 'note': 'iot'  },
    { 'name': 'VLAN1005', 'if':'eth1', 'vlan': 1005, 'mark': 1005, 'note': 'gaming'  },
    { 'name': 'VLAN1007', 'if':'eth1', 'vlan': 1007, 'mark': 1007, 'note': 'printer'  },
    { 'name': 'VLAN1009', 'if':'eth1', 'vlan': 1009, 'mark': 1009, 'note': 'guest'  },
]
default_action = 'drop'
log_default = True
exceptions = [
    { 'src': '*'       , 'dst': 'WAN',      'log': False, 'note': 'WAN access from all' },
#    { 'src': 'VLAN1002', 'dst': '*',        'log': False, 'note': 'Users can access all' },
    { 'src': 'VLAN1002', 'dst': 'LAN',      'log': False, 'note': 'Users to network infra' },
    { 'src': 'VLAN1002', 'dst': 'VLAN1004', 'log': False, 'note': 'Users to IoT devices ' },
    { 'src': 'VLAN1002', 'dst': 'VLAN1005', 'log': False, 'note': 'Users to gaming PC' },
    { 'src': 'VLAN1002', 'dst': 'VLAN1007', 'log': False, 'note': 'Users to printer' },
    { 'src': 'VLAN1005', 'dst': 'VLAN1007', 'log': False, 'note': 'Gaming PC to printer' },
]

firewall = make_firewall(networks, default_action, exceptions, log_default)
print(json.dumps(firewall, sort_keys=True, indent=4, separators=(',', ': ')))
