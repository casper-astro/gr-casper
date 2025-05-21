find_package(PkgConfig)

PKG_CHECK_MODULES(PC_GR_CASPER gnuradio-casper)

FIND_PATH(
    GR_CASPER_INCLUDE_DIRS
    NAMES gnuradio/casper/api.h
    HINTS $ENV{CASPER_DIR}/include
        ${PC_CASPER_INCLUDEDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/include
          /usr/local/include
          /usr/include
)

FIND_LIBRARY(
    GR_CASPER_LIBRARIES
    NAMES gnuradio-casper
    HINTS $ENV{CASPER_DIR}/lib
        ${PC_CASPER_LIBDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/lib
          ${CMAKE_INSTALL_PREFIX}/lib64
          /usr/local/lib
          /usr/local/lib64
          /usr/lib
          /usr/lib64
          )

include("${CMAKE_CURRENT_LIST_DIR}/gnuradio-casperTarget.cmake")

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(GR_CASPER DEFAULT_MSG GR_CASPER_LIBRARIES GR_CASPER_INCLUDE_DIRS)
MARK_AS_ADVANCED(GR_CASPER_LIBRARIES GR_CASPER_INCLUDE_DIRS)
