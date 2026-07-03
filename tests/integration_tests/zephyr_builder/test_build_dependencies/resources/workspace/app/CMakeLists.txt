cmake_minimum_required(VERSION 3.20)
project(moulin_builddep_integration C)
configure_file("../config/nonstandard-build.conf" "${CMAKE_BINARY_DIR}/nonstandard-build.conf" COPYONLY)
add_executable(fake_app src/main.c)
