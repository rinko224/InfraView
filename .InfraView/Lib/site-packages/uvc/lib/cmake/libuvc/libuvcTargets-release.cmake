#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "PLLibUVC::uvc" for configuration "Release"
set_property(TARGET PLLibUVC::uvc APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(PLLibUVC::uvc PROPERTIES
  IMPORTED_IMPLIB_RELEASE "${_IMPORT_PREFIX}/lib/uvc.lib"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/uvc.dll"
  )

list(APPEND _cmake_import_check_targets PLLibUVC::uvc )
list(APPEND _cmake_import_check_files_for_PLLibUVC::uvc "${_IMPORT_PREFIX}/lib/uvc.lib" "${_IMPORT_PREFIX}/bin/uvc.dll" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
