#!/usr/bin/python

"""
SPDX-License-Identifier: BSD-3-Clause
"""

from typing import Any, Mapping, Optional, List
import json
import sys
import clang.cindex
from clang.cindex import CursorKind, TypeKind


class Type:
    def __init__(self,
                 cursor,
                 types: Mapping[str, Any],
                 aliases: Mapping[str, str]):
        self.cursor = cursor
        self.types = types
        self.aliases = aliases

    def resolve(self) -> str:
        raise NotImplementedError

    def resolve_ffi_type(self) -> str:
        raise NotImplementedError


class Typedef(Type):
    def __init__(self, cursor, types, aliases):
        super().__init__(cursor, types, aliases)
        self.name = cursor.spelling

    def resolve(self) -> str:
        return self.name

    def resolve_ffi_type(self) -> str:
        underlying = self.cursor.underlying_typedef_type
        return self._resolve_underlying_ffi_type(underlying)

    def _resolve_underlying_ffi_type(self, typ):
        # Follow typedef chain
        if typ.kind == TypeKind.TYPEDEF:
            return self._resolve_underlying_ffi_type(typ.get_canonical())
        elif typ.kind == TypeKind.POINTER:
            return "pointer"
        elif typ.kind in (TypeKind.ULONG, TypeKind.LONG):
            return "ulong"
        elif typ.kind in (TypeKind.UCHAR, TypeKind.CHAR_S, TypeKind.CHAR_U):
            return "uchar"
        else:
            # Try to get it from types dict
            type_id = self._get_type_id(typ)
            if type_id in self.types:
                return self.types[type_id].resolve_ffi_type()
            return "pointer"  # default

    def _get_type_id(self, typ):
        decl = typ.get_declaration()
        if decl.kind != CursorKind.NO_DECL_FOUND:
            return str(decl.hash)
        return str(hash(typ.spelling))


class PointerType(Type):
    def __init__(self, cursor, pointee_type, types, aliases):
        super().__init__(cursor, types, aliases)
        self.pointee_type = pointee_type
        self.type_id = str(hash(str(pointee_type.spelling)))

    def resolve(self) -> str:
        # Check if there's an alias for this pointer type
        if self.type_id in self.aliases:
            return self.aliases[self.type_id]

        # Resolve the pointee type
        pointee_str = self._resolve_pointee()
        return f"{pointee_str} *"

    def _resolve_pointee(self) -> str:
        pointee = self.pointee_type

        # Handle typedef
        if pointee.kind == TypeKind.TYPEDEF:
            decl = pointee.get_declaration()
            return decl.spelling

        # Handle elaborated/record types
        if pointee.kind == TypeKind.ELABORATED:
            return pointee.get_canonical().spelling

        if pointee.kind == TypeKind.RECORD:
            decl = pointee.get_declaration()
            # Check for typedef alias
            type_id = str(decl.hash)
            if type_id in self.aliases:
                return self.aliases[type_id]
            return pointee.spelling

        # Handle const-qualified types
        if pointee.kind == TypeKind.CONSTANTARRAY:
            elem_type = pointee.get_array_element_type()
            return self._get_type_string(elem_type)

        # Handle function pointers
        if pointee.kind == TypeKind.FUNCTIONNOPROTO or pointee.kind == TypeKind.FUNCTIONPROTO:
            return "void"  # Simplified

        # Primitive types
        return self._get_type_string(pointee)

    def _get_type_string(self, typ):
        if typ.kind == TypeKind.TYPEDEF:
            return typ.get_declaration().spelling
        elif typ.kind == TypeKind.ULONG or typ.kind == TypeKind.LONG:
            return "long unsigned int"
        elif typ.kind == TypeKind.UCHAR or typ.kind == TypeKind.CHAR_U:
            return "unsigned char"
        elif typ.kind == TypeKind.VOID:
            return "void"
        else:
            return typ.spelling

    def resolve_ffi_type(self) -> str:
        return "pointer"


class FundamentalType(Type):
    def __init__(self, cursor, typ, types, aliases):
        super().__init__(cursor, types, aliases)
        self.typ = typ

    def resolve(self) -> str:
        if self.typ.kind == TypeKind.ULONG or self.typ.kind == TypeKind.LONG:
            return "long unsigned int"
        elif self.typ.kind == TypeKind.UCHAR or self.typ.kind == TypeKind.CHAR_U:
            return "unsigned char"
        return self.typ.spelling

    def resolve_ffi_type(self) -> str:
        # 8 bytes = 64 bits for ulong, 1 byte = 8 bits for uchar
        if self.typ.kind == TypeKind.ULONG or self.typ.kind == TypeKind.LONG:
            return "ulong"
        elif self.typ.kind == TypeKind.UCHAR or self.typ.kind == TypeKind.CHAR_U:
            return "uchar"
        return "pointer"


class CvQualifiedType(Type):
    def __init__(self, cursor, base_type, types, aliases):
        super().__init__(cursor, types, aliases)
        self.base_type = base_type

    def resolve(self) -> str:
        base_str = self._resolve_base()
        return f"const {base_str}"

    def _resolve_base(self) -> str:
        if self.base_type.kind == TypeKind.TYPEDEF:
            return self.base_type.get_declaration().spelling
        elif self.base_type.kind == TypeKind.POINTER:
            pointee = self.base_type.get_pointee()
            if pointee.kind == TypeKind.TYPEDEF:
                return pointee.get_declaration().spelling + " *"
            return pointee.spelling + " *"
        return self.base_type.spelling


class ElaboratedType(Type):
    def __init__(self, cursor, typ, types, aliases):
        super().__init__(cursor, types, aliases)
        self.typ = typ

    def resolve(self) -> str:
        canonical = self.typ.get_canonical()
        if canonical.kind == TypeKind.RECORD:
            decl = canonical.get_declaration()
            type_id = str(decl.hash)
            if type_id in self.aliases:
                return self.aliases[type_id]
            return canonical.spelling
        return canonical.spelling


class ArrayType(Type):
    def __init__(self, cursor, typ, types, aliases):
        super().__init__(cursor, types, aliases)
        self.typ = typ

    def resolve(self) -> str:
        elem_type = self.typ.get_array_element_type()
        size = self.typ.get_array_size()

        if elem_type.kind == TypeKind.TYPEDEF:
            elem_str = elem_type.get_declaration().spelling
        elif elem_type.kind == TypeKind.UCHAR or elem_type.kind == TypeKind.CHAR_U:
            elem_str = "unsigned char"
        else:
            elem_str = elem_type.spelling

        return f"{elem_str}[{size}]"


class Field(Type):
    def __init__(self, cursor, types, aliases):
        super().__init__(cursor, types, aliases)
        self.name = cursor.spelling
        self.field_type = cursor.type

    def to_json(self) -> Mapping[str, Any]:
        obj = {}
        obj["name"] = self.name
        obj["type"] = self._resolve_type()
        return obj

    def _get_type_spelling(self) -> str:
        typ = self.field_type

        # Handle arrays
        if typ.kind == TypeKind.CONSTANTARRAY:
            elem_type = typ.get_array_element_type()
            size = typ.get_array_size()
            if elem_type.kind == TypeKind.TYPEDEF:
                elem_str = elem_type.get_declaration().spelling
            elif elem_type.kind == TypeKind.UCHAR or elem_type.kind == TypeKind.CHAR_U:
                elem_str = "unsigned char"
            else:
                elem_str = elem_type.spelling
            return f"{elem_str}[{size}]"

        # Handle typedef
        if typ.kind == TypeKind.TYPEDEF:
            return typ.get_declaration().spelling

        # Handle pointers
        if typ.kind == TypeKind.POINTER:
            pointee = typ.get_pointee()
            if pointee.kind == TypeKind.TYPEDEF:
                return pointee.get_declaration().spelling + " *"
            elif pointee.kind == TypeKind.UCHAR or pointee.kind == TypeKind.CHAR_U:
                return "unsigned char *"
            elif pointee.kind == TypeKind.VOID:
                return "void *"
            return pointee.spelling + " *"

        # Handle record types
        if typ.kind == TypeKind.RECORD or typ.kind == TypeKind.ELABORATED:
            decl = typ.get_declaration()
            # Check for typedef alias
            type_id = str(decl.hash)
            if type_id in self.aliases:
                return self.aliases[type_id]
            canonical = typ.get_canonical()
            if canonical.kind == TypeKind.RECORD:
                decl = canonical.get_declaration()
                type_id = str(decl.hash)
                if type_id in self.aliases:
                    return self.aliases[type_id]
            return typ.spelling

        # Fundamental types
        if typ.kind == TypeKind.ULONG or typ.kind == TypeKind.LONG:
            return "long unsigned int"
        elif typ.kind == TypeKind.UCHAR or typ.kind == TypeKind.CHAR_U:
            return "unsigned char"

        return typ.spelling

    def _resolve_type(self) -> str:
        spelling = self._get_type_spelling()
        type_id = str(hash(str(spelling)))
        return self.aliases.get(type_id, spelling)


class Struct(Type):
    def __init__(self, cursor, types, aliases):
        super().__init__(cursor, types, aliases)
        self.name = cursor.spelling
        self.type_id = str(cursor.hash)
        self.members = []

    def resolve(self) -> str:
        if self.type_id in self.aliases:
            return self.aliases[self.type_id]
        return f"struct {self.name}"

    def to_json(self) -> Mapping[str, Any]:
        obj = {}
        if self.type_id in self.aliases:
            obj["name"] = self.aliases[self.type_id]
        else:
            obj["name"] = self.name
        obj["members"] = self.members
        return obj


class FunctionType(Type):
    pass


class Function(Type):
    def __init__(self, cursor, types, aliases):
        super().__init__(cursor, types, aliases)
        self.name = cursor.spelling
        self.result_type = cursor.result_type
        self.arguments = []
        self.version = 2

        # Collect arguments
        for arg in cursor.get_arguments():
            self.arguments.append({
                'name': arg.spelling,
                'type': arg.type
            })

    def to_json(self) -> Mapping[str, Any]:
        obj = {}
        obj["name"] = self.name
        obj["version"] = self.version
        obj["returns"] = self._resolve_type(self.result_type)
        obj["arguments"] = []

        for arg in self.arguments:
            obj["arguments"].append({
                "type": self._resolve_type(arg['type']),
                "name": arg['name'],
                "ffi-type": self._resolve_ffi_type(arg['type']),
            })

        return obj

    def _get_type_spelling(self, typ) -> str:
        # Handle typedef
        if typ.kind == TypeKind.TYPEDEF:
            return typ.get_declaration().spelling

        # Handle pointers
        if typ.kind == TypeKind.POINTER:
            pointee = typ.get_pointee()
            if pointee.kind == TypeKind.TYPEDEF:
                return pointee.get_declaration().spelling + " *"
            elif pointee.kind == TypeKind.ULONG or pointee.kind == TypeKind.LONG:
                return "long unsigned int *"
            elif pointee.kind == TypeKind.UCHAR or pointee.kind == TypeKind.CHAR_U:
                return "unsigned char *"
            elif pointee.kind == TypeKind.VOID:
                # Check if it's a typedef to void pointer
                if typ.kind == TypeKind.TYPEDEF:
                    return typ.get_declaration().spelling
                return "void *"
            return pointee.spelling + " *"

        # Handle fundamental types
        if typ.kind == TypeKind.ULONG or typ.kind == TypeKind.LONG:
            return "long unsigned int"
        elif typ.kind == TypeKind.UCHAR or typ.kind == TypeKind.CHAR_U:
            return "unsigned char"

        return typ.spelling

    def _resolve_type(self, typ) -> str:
        spelling = self._get_type_spelling(typ)
        type_id = str(hash(str(spelling)))
        return self.aliases.get(type_id, spelling)

    def _resolve_ffi_type(self, typ) -> str:
        # Handle typedef - need to resolve to underlying type
        if typ.kind == TypeKind.TYPEDEF:
            underlying = typ.get_canonical()
            return self._resolve_ffi_type(underlying)

        # Pointers are always "pointer"
        if typ.kind == TypeKind.POINTER:
            return "pointer"

        if typ.kind == TypeKind.ELABORATED:
            typ = typ.get_canonical()

        # Fundamental types
        if typ.kind == TypeKind.ULONG or typ.kind == TypeKind.LONG:
            return "ulong"
        elif typ.kind == TypeKind.UCHAR or typ.kind == TypeKind.CHAR_U:
            return "uchar"

        # Default to pointer for everything else
        return "pointer"


class Encoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "to_json"):
            return obj.to_json()
        else:
            return super().default(obj)


class AST:
    def __init__(self, translation_unit):
        self.tu = translation_unit
        self.cursor = translation_unit.cursor
        types = {}
        self.aliases = {}
        functions = {}
        self.structs = []
        self.origin = None

        # First pass: collect all typedefs to build alias map
        self._collect_typedefs(self.cursor)

        # Second pass: collect structs and functions
        self._collect_declarations(self.cursor, types, functions)

        # Determine origin file from C_GetInterfaceList function
        for func_name, func in functions.items():
            if func_name == 'C_GetInterfaceList':
                extent = func.cursor.extent
                if extent.start.file:
                    # Extract just the relative path if it contains the working directory
                    import os
                    file_path = extent.start.file.name
                    # Try to make it relative to current directory
                    try:
                        cwd = os.getcwd()
                        if file_path.startswith(cwd):
                            file_path = os.path.relpath(file_path, cwd)
                    except:
                        pass
                    self.origin = file_path
                break

        # Get function names from CK_FUNCTION_LIST structures
        function_names2 = self.get_function_names(2, types)
        function_names3 = self.get_function_names(3, types)

        self.functions = []
        for name in function_names3:
            if name in functions:
                function = functions[name]
                if name not in function_names2:
                    function.version = 3
                else:
                    function.version = 2
                self.functions.append(function)

    def _collect_typedefs(self, cursor):
        """First pass to collect all typedef aliases"""
        for child in cursor.get_children():
            # Skip system headers
            if child.location.file and not self._is_main_file(child.location.file):
                continue

            if child.kind == CursorKind.TYPEDEF_DECL:
                underlying = child.underlying_typedef_type

                # Map the underlying type to this typedef name
                if underlying.kind == TypeKind.POINTER:
                    pointee = underlying.get_pointee()
                    type_id = str(hash(str(f"{pointee.spelling} *")))
                    self.aliases[type_id] = child.spelling
                elif underlying.kind == TypeKind.RECORD or underlying.kind == TypeKind.ELABORATED:
                    decl = underlying.get_declaration()
                    if decl.kind != CursorKind.NO_DECL_FOUND:
                        type_id = str(decl.hash)
                        if not decl.spelling.startswith("CK_"):
                            self.aliases[type_id] = child.spelling
                        else:
                            print(decl.spelling)

            # Recurse into namespaces, etc.
            elif child.kind in (CursorKind.NAMESPACE, CursorKind.TRANSLATION_UNIT):
                self._collect_typedefs(child)

    def _collect_declarations(self, cursor, types, functions):
        """Second pass to collect all declarations"""
        for child in cursor.get_children():
            # Skip system headers
            if child.location.file and not self._is_main_file(child.location.file):
                continue

            if child.kind == CursorKind.STRUCT_DECL:
                # Skip incomplete/forward declarations
                if not child.is_definition():
                    continue

                # Skip non-CK_ structs
                name = child.spelling
                type_id = str(child.hash)

                # Use typedef name if available
                if type_id in self.aliases:
                    name = self.aliases[type_id]

                if not name.startswith("CK_"):
                    continue

                struct = Struct(child, types, self.aliases)

                # Collect members
                for member in child.get_children():
                    if member.kind == CursorKind.FIELD_DECL:
                        field = Field(member, types, self.aliases)
                        struct.members.append(field)

                self.structs.append(struct)
                types[type_id] = struct

            elif child.kind == CursorKind.FUNCTION_DECL:
                # Only collect functions starting with C_
                if child.spelling.startswith("C_"):
                    functions[child.spelling] = Function(child, types, self.aliases)

            # Recurse into namespaces, etc.
            elif child.kind in (CursorKind.NAMESPACE, CursorKind.TRANSLATION_UNIT):
                self._collect_declarations(child, types, functions)

    def _is_main_file(self, file):
        """Check if file is the main file being parsed (not a system header)"""
        if not file:
            return False
        # Simple heuristic: main file contains "pkcs11.h"
        return "pkcs11.h" in file.name

    def get_function_names(self, version, types):
        """Extract function names from CK_FUNCTION_LIST structures"""
        if version == 2:
            struct_name = "_CK_FUNCTION_LIST"
        else:
            struct_name = "_CK_FUNCTION_LIST_3_0"

        # Find the struct
        for struct in self.structs:
            if struct.name == struct_name:
                # Skip the first member (version) and return the rest
                names = []
                for member in struct.members[1:]:
                    names.append(member.name)
                return names

        return []


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("infile", type=argparse.FileType("r"))
    parser.add_argument("-o", "--outfile", type=argparse.FileType("w"),
                        required=False, default=sys.stdout)
    parser.add_argument('--clang-resource-dir', type=str)
    args = parser.parse_args()

    # Initialize libclang
    index = clang.cindex.Index.create()

    # Parse the header file
    clang_args = ['-x', 'c']
    if args.clang_resource_dir:
        clang_args += ['-resource-dir', args.clang_resource_dir]
    tu = index.parse(args.infile.name, args=clang_args)

    # Check for parse errors
    if tu.diagnostics:
        for diag in tu.diagnostics:
            if diag.severity >= clang.cindex.Diagnostic.Error:
                print(f"Error: {diag}", file=sys.stderr)

    # Build AST representation
    ast = AST(tu)

    # Generate JSON output
    with args.outfile:
        args.outfile.write(json.dumps({
            "comment": f"This file is automatically generated from {ast.origin}",
            "license": "BSD-3-Clause",
            "functions": ast.functions,
            "structs": ast.structs,
        },
                                      cls=Encoder, indent=2))
        args.outfile.write("\n")
