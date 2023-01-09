import logging
from logging import config

class ThreadMessageFilter(logging.Filter):
    """ Filter attached to root logger that will print to console and file messages
    from multiple nodes on their own threads.
    """
    def __init__(self, name):
        self.name = name

    # Filter through calls from other threads that are at a certain level
    # and also all calls from the main thread
    def filter(self, record):
        if record.levelno >= 20 and self.name != record.name:
            return True
        if self.name == record.name:
            return True
        else:
            return False

########################
### Configure Log file ###
########################
def configure_logging(name, filter=False, debug=False, to_console=False, filename='mylog.log'):
    """ This function configures logging facility.
    The current setup is for printing log messages onto console AND onto the file.
    Formatters are the same for both output destinations.
    Handing of log levels:
    - console output includes DEBUG messages or not depending on the `debug` argument.
    - file ouput includes all levels including DEBUG.
    """
    frmt_str = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
    frmt_out = '%(message)s'

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # set up logging to file
    file_handler = logging.FileHandler(filename)
    f_formatter = logging.Formatter(frmt_str)
    file_handler.setFormatter(f_formatter)
    logger.addHandler(file_handler)

    # define a handler for console
    if to_console == True:
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG if debug else logging.INFO)
        formatter = logging.Formatter(frmt_str)
        console.setFormatter(formatter)
        console.addFilter(ThreadMessageFilter(name))
        logger.addHandler(console)

    return logger
