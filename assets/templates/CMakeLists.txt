cmake_minimum_required(VERSION 3.23)

project(my_cpp_app VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CMAKE_CXX_VISIBILITY_PRESET hidden)
set(CMAKE_VISIBILITY_INLINES_HIDDEN ON)

option(BUILD_SHARED_LIBS "Build shared libraries by default" OFF)

include(CTest)
include(GNUInstallDirs)
include(GenerateExportHeader)

if(NOT DEFINED CMAKE_RUNTIME_OUTPUT_DIRECTORY)
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
endif()
if(NOT DEFINED CMAKE_LIBRARY_OUTPUT_DIRECTORY)
    set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")
endif()
if(NOT DEFINED CMAKE_ARCHIVE_OUTPUT_DIRECTORY)
    set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")
endif()

add_library(app_core
    src/core.cpp
)
add_library(my_cpp_app::core ALIAS app_core)

generate_export_header(app_core
    EXPORT_MACRO_NAME APP_CORE_API
    STATIC_DEFINE APP_CORE_STATIC_DEFINE
    EXPORT_FILE_NAME "${CMAKE_CURRENT_BINARY_DIR}/generated/include/my_cpp_app/app_core_export.h"
)
get_target_property(_app_core_type app_core TYPE)
if(_app_core_type STREQUAL "STATIC_LIBRARY")
    target_compile_definitions(app_core PUBLIC APP_CORE_STATIC_DEFINE)
endif()

target_include_directories(app_core
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}/generated/include>
        $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
)

set(_my_cpp_app_warnings
    $<$<CXX_COMPILER_FRONTEND_VARIANT:MSVC>:/W4>
    $<$<CXX_COMPILER_FRONTEND_VARIANT:MSVC>:/utf-8>
    $<$<CXX_COMPILER_ID:MSVC>:/permissive->
    $<$<NOT:$<CXX_COMPILER_FRONTEND_VARIANT:MSVC>>:-Wall>
    $<$<NOT:$<CXX_COMPILER_FRONTEND_VARIANT:MSVC>>:-Wextra>
    $<$<NOT:$<CXX_COMPILER_FRONTEND_VARIANT:MSVC>>:-Wpedantic>
)

target_compile_options(app_core PRIVATE ${_my_cpp_app_warnings})

add_executable(my_cpp_app
    apps/main.cpp
)
target_link_libraries(my_cpp_app PRIVATE my_cpp_app::core)
target_compile_options(my_cpp_app PRIVATE ${_my_cpp_app_warnings})
if(APPLE)
    set_target_properties(my_cpp_app PROPERTIES
        INSTALL_RPATH "@loader_path/../${CMAKE_INSTALL_LIBDIR}"
        BUILD_WITH_INSTALL_RPATH FALSE
    )
elseif(UNIX)
    set_target_properties(my_cpp_app PROPERTIES
        INSTALL_RPATH "$ORIGIN/../${CMAKE_INSTALL_LIBDIR}"
        BUILD_WITH_INSTALL_RPATH FALSE
    )
endif()

install(TARGETS my_cpp_app app_core
    EXPORT my_cpp_app_targets
    RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
    LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}"
    ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
)
install(EXPORT my_cpp_app_targets
    FILE my_cpp_appTargets.cmake
    NAMESPACE my_cpp_app::
    DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/my_cpp_app"
)
install(
    FILES "${CMAKE_CURRENT_BINARY_DIR}/generated/include/my_cpp_app/app_core_export.h"
    DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}/my_cpp_app"
)
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/include")
    install(
        DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/include/"
        DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
    )
endif()

if(BUILD_TESTING AND PROJECT_IS_TOP_LEVEL)
    # find_package(GTest CONFIG REQUIRED)
    # add_subdirectory(tests)
    # On Windows with BUILD_SHARED_LIBS=ON, copy runtime DLLs next to test executables:
    # add_custom_command(TARGET my_tests POST_BUILD
    #     COMMAND ${CMAKE_COMMAND} -E copy_if_different
    #         $<TARGET_RUNTIME_DLLS:my_tests> $<TARGET_FILE_DIR:my_tests>
    #     COMMAND_EXPAND_LISTS
    # )
endif()
