import logging

########################
### Configure Log file ###
########################
def configure_logging(name, debug=False, filename='mylog.log'):
    """ This function configures logging facility.
    The current setup is for printing log messages onto console AND onto the file.
    Formatters are the same for both output destinations.
    Handing of log levels:
    - console output includes DEBUG messages or not depending on the `debug` argument.
    - file ouput includes all levels including DEBUG.
    """
    frmt_str = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
    frmt_out = '%(message)s'

    # set up logging to file
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        logger.handlers = []
    logger.propagating = False

    file_handler = logging.FileHandler(filename)
    f_formatter = logging.Formatter(frmt_str)
    file_handler.setFormatter(f_formatter)
    logger.addHandler(file_handler)

    # define a handler for console
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if debug else logging.INFO)
    formatter = logging.Formatter(frmt_str)
    console.setFormatter(formatter)
    logger.addHandler(console)

    return logger
