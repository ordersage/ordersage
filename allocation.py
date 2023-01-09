class Allocation():
    def __init__(self, \
                 hostnames,
                 slices=None, context=None, \
                 site=None, hwtype=None, user=None, project=None,
                 certificate=None, \
                 private_key=None, public_key=None, geni_cache=None):
        self.hostnames = hostnames
        self.slices = slices
        self.context = context
        self.site = site
        self.hwtype = hwtype
        self.user = user
        self.project = project
        self.certificate = certificate
        self.private_key = private_key
        self.public_key = public_key
        self.geni_cache = geni_cache
