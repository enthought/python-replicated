===================
 python-replicated
===================

A Python interface to the Replicated_ `Vendor API`_.

.. _Replicated: https://www.replicated.com

.. _`Vendor API`: http://docs.replicated.com/docs/about-the-vendor-api


The library currently only provides access to a very limited subset of
the Replicated Vendor API.

The library is also currently untested.  This will be rectified soon.


Example usage
=============


There is not yet any real user documentation. Here is a brief example
of a limited subset of the library::

    from replicated.core import ReplicatedVendorAPI
    api = ReplicatedVendorAPI('token')
    apps = api.get_apps()
    app = apps[0]
    releases = list(app.releases)
    print(releases[0].config)
    releases[0].config = new_yaml_config
    print(releases[0].edited_at)
