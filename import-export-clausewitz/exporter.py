from pathlib import Path
import os
import io
import math

import bpy
import bmesh
import mathutils
from . import (pdx_data, utils)

class PdxFileExporter:
    """File Exporter Class"""
    def __init__(self, filename):
        self.filename = filename

    #Returns Array of Pdx_Meshs
    #Takes Mesh Object
    def splitMeshes(self, obj, transform_mat, boneIDs=None):
        print("Exporting and splitting Mesh...")

        result = []

        bmeshes = []
        materials = []
        faces_for_materials = {}

        print(obj)
        print(obj.data)
        mesh = obj.data

        print("Collecting Materials...")
        for mat_slot in obj.material_slots:
            if mat_slot.material is not None:
                faces_for_materials[mat_slot.material.name] = []
                materials.append(mat_slot.material.name)

        print(faces_for_materials)

        print("Getting Faces for Materials...")
        for face in mesh.polygons:
            #print("Face: ", face.index, " Material Index: ", face.material_index)
            slot = obj.material_slots[face.material_index]
            mat = slot.material

            if mat is not None:
                faces_for_materials[mat.name].append(face.index)
            else:
                print("No Material for Face: ", face.index, " in Slot: ", face.material_index)

        #print(faces_for_materials)

        bm_complete = bmesh.new()
        bm_complete.from_mesh(mesh)

        bm_complete.faces.ensure_lookup_table()
        bm_complete.verts.ensure_lookup_table()
        bm_complete.verts.index_update()
        bm_complete.faces.index_update()

        print(len(bm_complete.faces))

        for material in materials:
            removed_count = 0

            temp = bm_complete.copy()

            stray_vertices = []

            temp.faces.ensure_lookup_table()
            temp.verts.ensure_lookup_table()
            temp.verts.index_update()
            temp.faces.index_update()

            print("Removing Faces...")
            for index in faces_for_materials[material]:
                temp.faces.remove(temp.faces[index - removed_count])
                temp.faces.ensure_lookup_table()
                removed_count += 1

            for vert in temp.verts:
                if len(vert.link_faces) == 0:
                    stray_vertices.append(vert)

            print("Remove Stray Vertices...")
            for vert in stray_vertices:
                temp.verts.remove(vert)
                temp.verts.ensure_lookup_table()

            bmeshes.append(temp)

        # TODO: Split mesh if it has more than 40000 verts (maybe check for actual Clausewitz-Engine limitation)
        print("Triangulating Meshes...")
        for bm in bmeshes:
            bmesh.ops.triangulate(bm, faces=bm.faces)

        print("Generating PdxMeshes...")
        for bm in bmeshes:
            for vert in bm.verts:
                vert.co = vert.co * transform_mat

            bm.verts.index_update()
            bm.faces.index_update()
            bm.verts.ensure_lookup_table()

            normals = []
            verts = []
            tangents = []

            for i in range(len(bm.verts)):
                verts.append(bm.verts[i].co.copy())
                bm.verts[i].normal_update()
                normal_temp = bm.verts[i].normal * transform_mat
                normal_temp.normalize()
                normals.append(normal_temp)

            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            bm.verts.index_update()
            bm.faces.index_update()

            uv_coords = []
            uv_layer = bm.loops.layers.uv.active

            for face in bm.faces:
                for loop in face.loops:
                    uv_coords.append((0, 0))

            for face in bm.faces:
                for loop in face.loops:
                    uv_coords[loop.vert.index] = loop[uv_layer].uv.copy()
                    uv_coords[loop.vert.index][1] = 1 - uv_coords[loop.vert.index][1]

            max_index = 0

            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            bm.verts.index_update()
            bm.faces.index_update()

            for i in range(len(bm.verts)):
                if len(bm.verts[i].link_faces) > 0:#For Models with stray vertices...
                    tangents.append(bm.verts[i].link_faces[0].calc_tangent_vert_diagonal().to_4d() * transform_mat)
                else:
                    tangents.append((0.0, 0.0, 0.0, 0.0))

            #Trim data, remove empty bytes
            for i in range(len(uv_coords)):
                if uv_coords[i][0] == 0.0 and uv_coords[i][1] == 0.0:
                    max_index = i - 1
                    break

            del uv_coords[max_index:(len(uv_coords) - 1)]

            faces = []

            for face in bm.faces:
                temp = []

                for loop in face.loops:
                    temp.append(loop.vert.index)

                faces.append(temp)

            bb_min = [math.inf, math.inf, math.inf]
            bb_max = [-math.inf, -math.inf, -math.inf]

            for i in range(len(verts)):
                for j in range(3):
                    bb_min[j] = min([verts[i][j], bb_min[j]])
                    bb_max[j] = max([verts[i][j], bb_max[j]])

            result_mesh = pdx_data.PdxMesh()

            result_mesh.verts = verts
            result_mesh.normals = normals
            result_mesh.tangents = tangents
            result_mesh.uv_coords = uv_coords
            result_mesh.faces = faces
            result_mesh.meshBounds = pdx_data.PdxBounds(bb_min, bb_max)
            result_mesh.material = pdx_data.PdxMaterial()

            diff_file = "test_diff"

            # TODO: Implement Texture Export
            # if len(bpy.data.objects[name].material_slots) > 0:
            #     for mat_slot in bpy.data.objects[name].material_slots:
            #         for mtex_slot in mat_slot.material.texture_slots:
            #             if mtex_slot:
            #                 if hasattr(mtex_slot.texture, 'image'):
            #                     if mtex_slot.texture.image is None:
            #                         bpy.ops.error.message('INVOKE_SCREEN', message="The Texture Image file is not loaded")
            #                     else:
            #                         diff_file = os.path.basename(mtex_slot.texture.image.filepath)
            # else:
            #     diff_file = os.path.basename(bpy.data.meshes[name].uv_textures[0].data[0].image.filepath)

            # TODO: Get Skinning information

            result_mesh.material.shader = "PdxMeshShip"
            result_mesh.material.diff = diff_file
            result_mesh.material.spec = diff_file.replace("diff", "spec")
            result_mesh.material.normal = diff_file.replace("diff", "normal")

            result.append(result_mesh)


        print("Cleaning up BMesh...")
        bm_complete.free()
        for bm in bmeshes:
            print(bm)
            bm.free()

        print("Return resulting Meshes...")
        return result

    def export_mesh(self, name, boneIDs=None):
        eul = mathutils.Euler((0.0, 0.0, math.radians(180.0)), 'XYZ')
        eul2 = mathutils.Euler((math.radians(90.0), 0.0, 0.0), 'XYZ')
        mat_rot = eul.to_matrix() * eul2.to_matrix()
        mat_rot.invert_safe()

        transform_mat = bpy.data.objects[name].matrix_world * mat_rot.to_4x4()

        pdxObjects = []
        pdxObjects.append(pdx_data.PdxAsset())

        pdxLocators = pdx_data.PdxLocators()
        pdxWorld = pdx_data.PdxWorld()

        for obj in bpy.data.objects:
            if obj.select:
                if obj.type == "MESH":
                    if obj.parent is None:
                        pdxShape = pdx_data.PdxShape(obj.name)
                        pdxShape.meshes = self.splitMeshes(obj, transform_mat)
                        pdxWorld.objects.append(pdxShape)
                elif obj.type == "ARMATURE":
                    if obj.parent is None:
                        #Highly Inefficient for now
                        for child in bpy.data.objects:
                            if child.parent == obj:
                                pdxSkeleton = pdx_data.PdxSkeleton()
                                boneIDs = {}

                                for i in range(len(obj.data.bones)):
                                    bone = obj.data.bones[i]
                                    boneIDs[bone.name] = i

                                for i in range(len(obj.data.bones)):
                                    bone = obj.data.bones[i]
                                    print(bone.name)
                                    print(str(boneIDs[bone.name]))
                                    pdxJoint = pdx_data.PdxJoint(bone.name)
                                    pdxJoint.index = i
                                    print(str(bone.parent))
                                    if bone.parent is not None:
                                        print(str(boneIDs[bone.parent.name]))
                                        pdxJoint.parent = boneIDs[bone.parent.name]
                                    else:
                                        print("Root Bone")

                                    pdxSkeleton.joints.append(pdxJoint)

                                pdxShape = pdx_data.PdxShape(obj.name)
                                pdxShape.skeleton = pdxSkeleton
                                pdxShape.meshes = self.splitMeshes(obj.children[0], transform_mat, boneIDs)

                                pdxWorld.objects.append(pdxShape)
                elif obj.type == "EMPTY":
                    if obj.parent is not None and obj.parent.name.lower() == "locators":
                        locator = pdx_data.PdxLocator(obj.name, obj.location * transform_mat)
                        obj.rotation_mode = 'QUATERNION'
                        locator.quaternion = obj.rotation_quaternion
                        #TODO locator.parent

                        pdxLocators.locators.append(locator)
                else:
                    print("Exporter: Invalid Type Selected: " + obj.type)

        pdxObjects.append(pdxWorld)

        if len(pdxLocators.locators) > 0:
            pdxObjects.append(pdxLocators)

        result_file = io.open(self.filename, 'w+b')

        result_file.write(b'@@b@')
        
        print(pdxObjects)

        for i in range(len(pdxObjects)):
            result_file.write(pdxObjects[i].get_binary_data())

        result_file.close()
"""

        world = pdx_data.PdxWorld([])

        if name.endswith("MeshShape"):
            shape = pdx_data.PdxShape(name)
        else:
            shape = pdx_data.PdxShape(name + ":MeshShape")

        mesh = pdx_data.PdxMesh()
        shape.mesh = mesh

        blender_mesh = bpy.data.meshes[name]

        bm = bmesh.new()
        bm.from_mesh(blender_mesh)
        bmesh.ops.triangulate(bm, faces=bm.faces)

        for vert in bm.verts:
            vert.co = vert.co * transform_mat

        bm.verts.index_update()
        bm.faces.index_update()
        bm.verts.ensure_lookup_table()

        normals = []
        verts = []
        tangents = []

        for i in range(len(bm.verts)):
            verts.append(bm.verts[i].co)
            bm.verts[i].normal_update()
            normal_temp = bm.verts[i].normal * transform_mat
            normal_temp.normalize()
            #temp_y = normal_temp[1]
            #normal_temp[1] = normal_temp[2]
            #normal_temp[2] = temp_y
            normals.append(normal_temp)

        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        bm.faces.index_update()

        uv_coords = []
        uv_layer = bm.loops.layers.uv.active

        for face in bm.faces:
            for loop in face.loops:
                uv_coords.append((0, 0))

        for face in bm.faces:
            for loop in face.loops:
                uv_coords[loop.vert.index] = loop[uv_layer].uv
                uv_coords[loop.vert.index][1] = 1 - uv_coords[loop.vert.index][1]

        max_index = 0

        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        bm.faces.index_update()

        for i in range(len(bm.verts)):
            if len(bm.verts[i].link_faces) > 0:#For Models with stray vertices...
                tangents.append(bm.verts[i].link_faces[0].calc_tangent_vert_diagonal().to_4d() * transform_mat)#(0.0, 0.0, 0.0, 0.0))
            else:
                tangents.append((0.0, 0.0, 0.0, 0.0))

        #Trim data, remove empty bytes
        for i in range(len(uv_coords)):
            #print(uv_coords[i])
            if uv_coords[i][0] == 0.0 and uv_coords[i][1] == 0.0:
                max_index = i - 1
                break

        del uv_coords[max_index:(len(uv_coords) - 1)]

        faces = []

        for face in bm.faces:
            temp = []

            for loop in face.loops:
                temp.append(loop.vert.index)

            faces.append(temp)

        bb_min = [math.inf, math.inf, math.inf]
        bb_max = [-math.inf, -math.inf, -math.inf]

        for i in range(len(verts)):
            for j in range(3):
                bb_min[j] = min([verts[i][j], bb_min[j]])
                bb_max[j] = max([verts[i][j], bb_max[j]])

        mesh.verts = verts
        mesh.normals = normals
        mesh.tangents = tangents
        mesh.uv_coords = uv_coords
        mesh.faces = faces
        mesh.meshBounds = pdx_data.PdxBounds(bb_min, bb_max)
        mesh.material = pdx_data.PdxMaterial()

        diff_file = ""

        if len(bpy.data.objects[name].material_slots) > 0:
            for mat_slot in bpy.data.objects[name].material_slots:
                for mtex_slot in mat_slot.material.texture_slots:
                    if mtex_slot:
                        if hasattr(mtex_slot.texture, 'image'):
                            if mtex_slot.texture.image is None:
                                bpy.ops.error.message('INVOKE_SCREEN', message="The Texture Image file is not loaded")
                            else:
                                diff_file = os.path.basename(mtex_slot.texture.image.filepath)
        else:
            diff_file = os.path.basename(bpy.data.meshes[name].uv_textures[0].data[0].image.filepath)

        mesh.material.shader = "PdxMeshShip"
        mesh.material.diff = diff_file
        mesh.material.spec = "test_spec"
        mesh.material.normal = "test_normal"

        #Collision Mesh
        collisionObject = None
        collisionShape = None

        for o in bpy.data.objects:
            if o.type == "MESH" and o.draw_type == "WIRE":
                collisionObject = o

        if collisionObject is None:
            print("WARNING ::: No Collision Mesh found. Only using Bounding Box!")
        else:
            print("Collision Shape Name: " + collisionObject.name)
            collisionShape = pdx_data.PdxShape(collisionObject.name)

            collisionMesh = pdx_data.PdxCollisionMesh()
            collisionShape.mesh = collisionMesh

            collision_blender_mesh = bpy.data.meshes[collisionObject.name]

            cbm = bmesh.new()
            cbm.from_mesh(collision_blender_mesh)
            bmesh.ops.triangulate(cbm, faces=cbm.faces)

            for vert in cbm.verts:
                vert.co = vert.co * transform_mat

            cbm.verts.index_update()
            cbm.faces.index_update()
            cbm.verts.ensure_lookup_table()

            cverts = []

            for i in range(len(cbm.verts)):
                cverts.append(cbm.verts[i].co)

            cbm.faces.ensure_lookup_table()
            cbm.verts.ensure_lookup_table()
            cbm.verts.index_update()
            cbm.faces.index_update()

            cfaces = []

            for face in cbm.faces:
                temp = []

                for loop in face.loops:
                    temp.append(loop.vert.index)

                cfaces.append(temp)

            cbb_min = [math.inf, math.inf, math.inf]
            cbb_max = [-math.inf, -math.inf, -math.inf]

            for i in range(len(cverts)):
                for j in range(3):
                    cbb_min[j] = min([cverts[i][j], cbb_min[j]])
                    cbb_max[j] = max([cverts[i][j], cbb_max[j]])

            collisionMesh.verts = cverts
            collisionMesh.faces = cfaces
            collisionMesh.meshBounds = pdx_data.PdxBounds(cbb_min, cbb_max)
            collisionMesh.material = pdx_data.PdxMaterial()

        world.objects.append(shape)
        if collisionShape is not None:
            world.objects.append(collisionShape)
        world.objects.append(locators)
        objects.append(world)


"""