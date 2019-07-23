# Unifi configuration stuff

Author: Tuomas Aura, Aalto University, tuomas.aura@aalto.fi

# Zone-based IPv6 firewall rules for Unifi Security Gateway

## Description

Python 3 script to generate zone-based IPv6 firewall rules for Unifi Security Gateway.

Firewall configuration in the Unifi Controller does not currently support IPv6 networks that obtain the IPv6 address prefix from the ISP with Prefix Delegation (DHCPv6-PD). However, it is possible to manually configure the firewall rules by uploading a `config.gateway.json` file to the Unifi Security Gateway. 

This Python 3 script generates "manual" configuration rules to mark incoming packets at each interface of the gateway (similar to `iptables --set-mark`) and to filter outgoing packets at each interface based on the marking. That is, the generated rules filter packets based on the incoming-outgoing interface pair - without referencing the source or destination IPv6 addresses. Thus, they work nicely with PD, where IPv6 address prefix is unknown when we receive it from the ISP:

The generated rules can coexist with other IPv6 firewall rules configured in the Controller web interface. Traffic will pass if it is accepted by both the generated rules and the Controller rules. The combination of script-generated zone-based rules and the Controller default rules for IPv6 should be a reasonable ruleset for most networks.
 
## Installing

1. Edit the network example at the end of the script to match the subnetworks and interfaces in your Security Gateway. Run the script: 

```bash
python3 zone_fw_ipv6.py > out.json
```

2. Merge the output manually to your `config.gateway.json` file. Take care to merge overlapping parts of the JSON tree. If you don't yet have such a file, you can simply rename the script output to `config.gateway.json`. 

3. Upload the file to the Unifi Security Gateway:

```bash
scp config.gateway.json root@CONTROLLER.IP:/var/lib/unifi/sites/XXXXXXXX/
ssh root@CONTROLLER.IP chown -R unifi:unifi /var/lib/unifi/
```
Above, replace `CONTROLLER.IP` with the address of your controller. Also, replace `XXXXXXXX` with the site identifier, which is either `default` or a short alpha-numeric string. The side identifier is part of the URL when viewing the side in the Controller web interface. The above path is for a Ubuntu controller; if using the Cloud Key, replace the destination path with `/srv/unifi/data/sites/XXXXXXXX/`.

Setting the permissions is necessary in some case, such as when uploading the file for the first time.

4. In the Unifi Controller web interface: select *Devices / GATEWAY_NAME / Config / Manage device /Provision*. 

5. Check in *Devices* that the provisioning completes. 

## Error recovery

When provisioning, any errors in the configuration will show under *Alerts*. You can also follow the controller log:

```bash
ssh root@ucc.it-aura.fi tail -f /var/log/unifi/server.log
```
Errors in the configuration can be fixed by uploading a new `config.gateway.json` file and waiting for the provisioning to complete. This often includes a reboot of the gateway and, thus, a brief network outage at the site. Errors in the IPv6 configuration should not impair IPv4  connectivity of the site any further than that. If desperate, simply delete the broken configuration file:

```bash
ssh root@CONTROLLER.IP rm /var/lib/unifi/sites/XXXXXXXX/config.gateway.json
```
Once the gateway has been provisioned, you can also ssh to the gateway and raview the configuration in both EdgeRouter and JSON formats:

```bash
ssh admin@GATEWAY.IP
show configuration
mca-ctrl -t dump-cfg 
```

## Discussion

Marking packets seems currently the only way to implement firewall rules between IPv6 subnets in a Unifi Security Gateway that receives its IPv6 address prefix with DHCPv6-PD. There may be a performance penalty related to the marking, although I have not done any measurements. A better solution would be for Unifi to implement IPv6 rules that update dynamically when the gateway receives a new PD prefix from the ISP. 

EdgeRouter suffers from the same problem. The generated rules would also work for EdgeRouter, but the configuration syntax is slightly different. The `config.gateway.json` file is a JSONified version of standard EdgeRouter configuration entries.  

Some web pages suggest filtering cross-subnet traffic with IPv6 address masks that match only the IPv6 Prefix Id (e.g. `"source": { "address": "::02:0:0:0:0/::ff:0:0:0:0" }` to match the Prefix Id 2). This would work correctly for cross-subnet traffic, but the filtering rules will also drop some packets from the Internet when they accidentally match the Prefix Id.

The problem is specific to IPv6 and PD. In comparison, IPv4 does not need packet marking because there is a NAT and the local subnets have fixed private prefixes. Also, if your network has a fixed IPv6 prefix, regular firewall rules are sufficient, and no packet marking is needed.  

## TODO

* Output also in EdgeRouter `config.boot` format. 
* Would it be better to reject than drop? 
* Are default rules from Controller sufficient to filter packets to gateway (LOCAL IN), or could zone-based rules be more specific? (E.g. Could limit ICMP types based on the VLAN.)
* Systematic testing of the generate firewall rules (currently only ad-hoc testing).

## License

This project is licensed under the MIT License. See the [LICENSE.txt](LICENSE.txt) file for details.
