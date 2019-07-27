# Unifi and EdgeRouter configuration stuff

Author: Tuomas Aura, Aalto University, tuomas.aura@aalto.fi

# Zone-based IPv6 firewall rules for Unifi Security Gateway

## Description

Python 3 script to generate zone-based IPv6 firewall rules for Unifi Security Gateway. It is intended for the following situations:

*Subnet isolation and DHCPv6-PD*: IPv6 firewall configuration in the Unifi Controller does not currently support networks that obtain their IPv6 prefix from the ISP with Prefix Delegation (DHCPv6-PD). The IPv6 firewall settings require the administrator to know the network prefix, but the prefix from PD is unknown and may change over time.

*Subnet isolation and DHCPv6 relay*: In a large network that manages IPv6 addresses centrally, it may be desirable to isolate physical subnets with a firewall while still obtaining the IPv6 addresses from a central DHCPv6 server through a DHCPv6 relay (details not discussed here). Again, it is impossible to creater the IPV6 firewall rules in the Unifi Controller because the administrator does not know which addresses will be on which side of the firewall. 

*Easier IPV6 firewall configuration*: Sometimes the network administrator knows the IPv6 prefix and which addresses are allocated to each subnet but prefers firewall rules that just work without copying the prefix to every rule. 

In such situations, it is necessary to set up a *zone-based firewall that filters IPV6 traffic between gateway interfaces and VLANs without any knowledge of the IPv6 prefixes*. It is possible to manually configure such a zone-based firewall in Unifi by setting up a `config.gateway.json` file. (In EdgeRouter, the same can be done with the `configure` CLI.)

This Python 3 script generates configuration rules for the Unifi Security Gateway to mark incoming packets at each interface of the gateway (similar to `iptables --set-mark`) and to filter outgoing packets at each interface based on the marking. That is, the generated rules filter packets based on the IN-OUT interface pair - without any reference to the source or destination IPv6 addresses. Thus, the rules work nicely with DHCPv6-PD and DHCPv6 relay. 

The generated rules can coexist with other IPv6 firewall rules configured in the Controller web interface. Traffic will pass if it is accepted by both the generated rules and the Controller rules. For most networks, it is probably sufficient to add the sript-generated zone-based rules to the default rules created by the Unifi Controller.
 
## Installing

1. Edit the network example at the end of the script to match the subnetworks and interfaces in your Security Gateway. 

2. Run the script: 

```bash
python3 zone_fw_ipv6.py > out.json
```

3. Merge the output manually to your `config.gateway.json` file. Take care to merge overlapping parts of the JSON tree. If you don't yet have such a file, you can simply rename the script output to `config.gateway.json`. 

4. Upload the file to the Unifi Security Gateway:

```bash
scp config.gateway.json root@CONTROLLER.IP:/var/lib/unifi/sites/XXXXXXXX/
ssh root@CONTROLLER.IP chown -R unifi:unifi /var/lib/unifi/
```
Above, replace `CONTROLLER.IP` with the address of your controller. Also, replace `XXXXXXXX` with the site identifier, which is either `default` or a short alpha-numeric string. (The site identifier is part of the URL when viewing the side in the Controller web interface.) The above path is for a Ubuntu-based controller; if using the Cloud Key, replace the destination path with `/srv/unifi/data/sites/XXXXXXXX/`.

Setting the permissions is necessary in some cases, such as when uploading the file for the first time. 

5. In the Unifi Controller web interface, select *Devices / GATEWAY_NAME / Config / Manage device / Provision*. Check in *Devices* that the provisioning completes. 

## Error recovery

When provisioning, any errors in the configuration will show under *Alerts*. You can also follow the controller log:

```bash
ssh root@CONTROLLER.IP tail -f /var/log/unifi/server.log
```

Errors in the configuration can be fixed by uploading a new `config.gateway.json` file and waiting for the provisioning to complete. This error recovery often includes an automated reboot of the gateway and, thus, a brief network outage at the site. Errors in the IPv6 configuration should not impair IPv4 connectivity of the site any further than that. If desperate, simply delete the broken configuration file:

```bash
ssh root@CONTROLLER.IP rm /var/lib/unifi/sites/XXXXXXXX/config.gateway.json
```
Once the gateway has been provisioned, you can ssh to the gateway, review the configuration in both EdgeRouter and JSON formats, and check the firewall statistics and live log feed:

```bash
ssh admin@GATEWAY.IP
show configuration
mca-ctrl -t dump-cfg 
show firewall
tail -f /var/log/messages
```

## Discussion

Marking packets seems currently the only way to implement firewall rules between IPv6 subnets in a Unifi Security Gateway that receives its IPv6 prefix with DHCPv6-PD. There may be a performance penalty related to the marking, although I have not done measurements. A better solution would be for Unifi to implement IPv6 rules that update dynamically when the gateway receives a new PD prefix from the ISP's DHCPv6 server. 

EdgeRouter needs a similar solution for IPv6 firewall and DHCPv6-PD. The generated rules would also work for EdgeRouter, but the configuration syntax is slightly different. The `config.gateway.json` file is a JSONified version of standard EdgeRouter configuration entries.  

In terms of netfilter, the packets are marked in the pre-routing mangle table and the filtering is done in the post-routing mangle table. Luckily, these tables are not used by the IPv6 firewall rules created by the Unifi Controller. Therefore, the two rulesets can coexit.

Some web pages suggest filtering cross-subnet traffic with IPv6 address masks that match only the IPv6 Prefix Id (e.g. `"source": { "address": "::02:0:0:0:0/::ff:0:0:0:0" }` to match the Prefix Id 2). This would work correctly for cross-subnet traffic, but the filtering rules will also drop some packets from the Internet when they accidentally match the Prefix Id. Thus, it is not a real solution.

The problem is specific to IPv6 and DHCPv6-PD (or DHCPv6 relay). In comparison, IPv4 does not need packet marking because there is a NAT at the gateway and the local subnets have fixed private prefixes, which can be used in the filtering rules. Also, if your network has a fixed IPv6 prefix, regular firewall rules based on address prefixes are sufficient, and no packet marking is needed. 

## TODO

* Output also in EdgeRouter `config.boot` format. 
* Would it be better to reject than drop? 
* Are default rules from Controller sufficient to filter packets to gateway (LOCAL IN), or could zone-based rules be more specific? (E.g. could limit ICMP types accepted from each VLAN.)
* Systematic testing of the generates firewall rules (currently only ad-hoc testing).
* Test rules with `default_action='accept'` in a real network (currently tested only with default action `drop`).

## License

This project is licensed under the MIT License. See the [LICENSE.txt](LICENSE.txt) file for details.
