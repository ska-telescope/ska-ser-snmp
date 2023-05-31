# ska-low-itf-devices

This project provides Tango device access to LOW ITF hardware
within the [Square Kilometre Array](https://skatelescope.org/).

Documentation
-------------

[![Documentation Status](https://readthedocs.org/projects/ska-telescope-ska-low-itf-devices/badge/?version=latest)](https://developer.skao.int/projects/ska-low-itf-devices/en/latest/?badge=latest)

The documentation for this project, including how to get started with it, can be found in the `docs` folder, or browsed in the SKA development portal:

* [ska-low-itf-devices documentation](https://developer.skatelescope.org/projects/ska-low-itf-devices/en/latest/index.html "SKA Developer Portal: ska-low-itf-devices documentation")

# ska_snmp_device.SNMPDevice

This is a generic SNMP Tango device class for monitoring and control of any
device that supports SNMP. It's configured using a YAML definition file, which
maps SNMP objects to Tango attributes, which are dynamically created when the
device is initialised. Here's a basic example defining a single attribute:

```yaml
attributes:
  - name: deviceDescription
    oid: [ SNMPv2-MIB, sysDescr, 0 ]
```

Attributes are defined with reference to SNMP MIBs - files that describe which
SNMP objects are available on a particular device. The `oid` field is made up
of a MIB name ("SNMPv2-MIB" in the example above), an object name ("sysDescr")
and one or more indexes. For more info about these, see below.

The most important Tango properties supported by SNMPDevice are:
* `DeviceDefinition`, the path to a device definition YAML file
* `Host`, the IP or DNS name of the SNMP endpoint of the device under control
* `Port`, the port of the SNMP endpoint, which defaults to 161
* `Community`, the SNMPv2 community name to use

## The device definition file syntax

The following file defines a minimal device for an Enlogic EN6808 PDU, with
attributes for reporting and setting the state of each of the 24 outlets.

```yaml
attributes:
  - name: deviceDescription
    oid: [ SNMPv2-MIB, sysDescr, 0 ]
    polling_period: .inf
    
  - name: firmwareVersion
    oid: [ ENLOGIC-PDU-MIB, pduNamePlateFirmwareVersion, 1 ]
    polling_period: .inf

  - name: serialNumber
    oid: [ ENLOGIC-PDU-MIB, pduNamePlateSerialNumber, 1 ]
    polling_period: .inf

  - name: outlet{}State
    oid: [ENLOGIC-PDU-MIB, pduOutletSwitchedSTATUSState, 1]
    indexes:
      - [1, 24]

  - name: outlet{}Command
    oid: [ENLOGIC-PDU-MIB, pduOutletSwitchedControlCommand, 1]
    indexes:
      - [1, 24]
    polling_period: 10000
```

### `name`

Pretty straightforward. This defines the Tango attribute's name. But note the
`{}`s in `outlet{}Command` and `outlet{}State` - these are placeholders which
are used when `indexes` is defined.

### `oid`

Defines the SNMP object this attribute will represent, in the form
`<mib-name>, <object name>, [<index>, ...]`.

The MIB name must correspond to a MIB file present on the filesystem, in
`$PWD/resources/mibs`, `/usr/share/snmp/mibs`, or `/usr/share/mibs` (these
last two are defaults from PySNMP, the SNMP library we use under the hood).
Any MIBs that the selected MIB imports from must ALSO exist in one of those
directories.

The object name should be one that's defined within the specified MIB file.

The indexes provided as part of the `oid` field will depend on the object.
Scalar objects - those that aren't part of an SNMP table - should always be
specified with the single index `0`. Tabular objects' indexes will depend on
the table definition.

If the `indexes` key is defined, the OID will be extended as described below.

### `indexes`

SNMP objects can either be scalar - that is, there is only one of them - or
part of a table, in which case multiple indexed instances of the object exist.
With `indexes` we can define attributes for tabular objects without having to
repeat ourselves for every instance.

When `indexes` is present, an attribute is created for each item in the range
specified by `indexes` - in this case, 1 to 24. The `name` field is templated
(as a Python format string) with the index value. In the example above, the
device would end up with attributes `outlet1State`, `outlet2State`, etc. The
index value will be appended to the `oid` for each attribute.

For example, the `outlet{}State` definition above is equivalent to

```yaml
  - name: outlet1State
    oid: [ENLOGIC-PDU-MIB, pduOutletSwitchedSTATUSState, 1, 1]
  - name: outlet2State
    oid: [ENLOGIC-PDU-MIB, pduOutletSwitchedSTATUSState, 1, 2]

...outlets 3 to 23...

  - name: outlet24State
    oid: [ENLOGIC-PDU-MIB, pduOutletSwitchedSTATUSState, 1, 24]
```


### `polling_period`

It's handy to be able to query different SNMP objects at different rates. For
example, the value of the `serialNumber` attribute above will never change.
`polling_period` sets the minimum time between polls for each attribute. The
default is to query the SNMP object on every iteration of the internal polling
loop, which by default runs every two seconds.

Setting `polling_period: 10000` means the object won't be queried any more
frequently than once every 10 seconds. Setting it to `polling_period: .inf`
means it will be polled only once.

## More about MIBs and OIDs

SNMP objects are organised in a global hierarchy. Each object is given an OID
which is a globally-unique sequence of numbers - for example, the OID for the
`sysDescr` object in the definition above is
[1.3.6.1.2.1.1.1](https://oidref.com/1.3.6.1.2.1.1.1). Each object defined in
a MIB also has a textual representation, which we use in our definition file.

Read more about how MIBs and OIDs work [here](https://kb.paessler.com/en/topic/653-how-do-snmp-mibs-and-oids-work).

## Providing multiple `indexes`

You'll note that in the examples, `indexes` is a list of lists. Usually you
will only need to provide one index for an attribute, but it's possible to
provide more. For example, the `pduOutletSwitchedSTATUSState` object we refer
to above actually has two indexes - the first indicates the PDU ID, the second
indicates the outlet ID. However, since we aren't dealing with daisy-chained
PDUs, we just baked the fixed PDU ID `1` into the `oid` field in our example.

When multiple indexes are provided, one attribute is created for each element
of the cartesian product of each of the indexes. For example, if you have
indexes `[1, 2]` and `[5, 6]`, attributes will be created for the index values
`(1, 5)`, `(1, 6)`, `(2, 5)` and `(2, 6)`. These values will be appended to
the attributes' OIDs, and passed positionally to Python's `str.format()` when
generating the attributes' names.

Our outlet state attribute above could have been defined more verbosely as:
```yaml
  - name: outlet{1}State
    oid: [ENLOGIC-PDU-MIB, pduOutletSwitchedSTATUSState]  # no indexes here!
    indexes:
      - [1, 1]
      - [1, 24]
```
Note we use `{1}` instead of `{}` in the name template - this means we're
referring to the second (zero-indexed) index value.
