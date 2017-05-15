import bpy
import bmesh
import mathutils
import math
import os
import io
from pathlib import Path
from . import (pdx_data, utils)

class PdxFileImporter:
    def __init__(self, filename):
        print("------------------------------------")
        print("Importing: " + filename + "\n\n\n\n\n")
        self.file = pdx_data.PdxFile(filename)
        self.file.read()

    def import_mesh(self):
        eul = mathutils.Euler((0.0, 0.0, math.radians(180.0)), 'XYZ')
        eul2 = mathutils.Euler((math.radians(90.0), 0.0, 0.0), 'XYZ')
        mat_rot = eul.to_matrix() * eul2.to_matrix()
        mat_rot.resize_4x4()

        for node in self.file.nodes:
            if isinstance(node, pdx_data.PdxAsset):
                print("Importer: PDXAsset")#TODOs
            elif isinstance(node, pdx_data.PdxWorld):
                for shape in node.objects:
                    if isinstance(shape, pdx_data.PdxShape):
                        name = shape.name

                        if isinstance(shape.skeleton, pdx_data.PdxSkeleton):
                            print("Importer: PdxSkeleton")
                            amt = bpy.data.armatures.new(name)
                            obj = bpy.data.objects.new(name, amt)
 
                            scn = bpy.context.scene
                            scn.objects.link(obj)
                            scn.objects.active = obj
                            obj.select = True

                            names = [""] * len(shape.skeleton.joints)

                            for joint in shape.skeleton.joints:
                                names[joint.index] = joint.name

                            bpy.ops.object.mode_set(mode='EDIT')

                            #parentTransforms = {}
                            
                            for joint in shape.skeleton.joints:
                                bone = amt.edit_bones.new(joint.name)

                                #print("Loading Joint \"" + joint.name + "\\" + str(joint.index) + "\"")
                                #print("Parent: \"" + names[joint.parent] + "\\" + str(joint.parent) + "\"")
                                #print("Transformation Matrix: ")

                                #print(str(joint.transform[0]) + "|" + str(joint.transform[1]) + "|" + str(joint.transform[2]) + "|" + str(joint.transform[3]))
                                #print(str(joint.transform[4]) + "|" + str(joint.transform[5]) + "|" + str(joint.transform[6]) + "|" + str(joint.transform[7]))
                                #print(str(joint.transform[8]) + "|" + str(joint.transform[9]) + "|" + str(joint.transform[10]) + "|" + str(joint.transform[11]))

                                #transformationMatrix = mathutils.Matrix((joint.transform[0:3], joint.transform[4:7], joint.transform[8:11]))
                                transformationMatrix = mathutils.Matrix()
                                transformationMatrix[0][0:4] = joint.transform[0], joint.transform[3], joint.transform[6], joint.transform[9]
                                transformationMatrix[1][0:4] = joint.transform[1], joint.transform[4], joint.transform[7], joint.transform[10]
                                transformationMatrix[2][0:4] = joint.transform[2], joint.transform[5], joint.transform[8], joint.transform[11]
                                transformationMatrix[3][0:4] = 0, 0, 0, 1
                                #parentTransforms[joint.index] = transformationMatrix
                                print(transformationMatrix.decompose())

                                if joint.parent >= 0:
                                    temp_transform = transformationMatrix #.inverted()
                                    components = temp_transform.decompose()

                                    parent = amt.edit_bones[names[joint.parent]] 
                                    bone.parent = parent
                                    bone.use_connect = True 

                                    mat_temp = components[1].to_matrix()
                                    mat_temp.resize_4x4()

                                    bone.tail = components[0] * mat_temp * mat_rot

                                    #bone.tail = parent.tail + (mathutils.Vector((1, 1, 1)) * transformationMatrix * mat_rot)

                                    #transformationMatrix *= parentTransforms[joint.parent]
                                else:          
                                    bone.head = (0,0,0)
                                    bone.tail = (0,0,0)


                                

                            bpy.ops.object.mode_set(mode='OBJECT')

                        print(str(len(shape.meshes)))
                        for meshData in shape.meshes:
                            if isinstance(meshData, pdx_data.PdxMesh):
                                mesh = bpy.data.meshes.new(name)
                                obj = bpy.data.objects.new(name, mesh)
                                
                                scn = bpy.context.scene
                                scn.objects.link(obj)
                                scn.objects.active = obj
                                obj.select = True
                                
                                mesh.from_pydata(meshData.verts, [], meshData.faces)

                                bm = bmesh.new()
                                bm.from_mesh(mesh)

                                for vert in bm.verts:
                                    vert.co = vert.co * mat_rot

                                bm.verts.ensure_lookup_table()
                                bm.verts.index_update()
                                bm.faces.index_update()

                                if meshData.material.shader == "Collision":
                                    obj.draw_type = "WIRE"
                                else:
                                    uv_layer = bm.loops.layers.uv.new(name + "_uv")

                                    for face in bm.faces:
                                        for loop in face.loops:
                                            loop[uv_layer].uv[0] = meshData.uv_coords[loop.vert.index][0]
                                            loop[uv_layer].uv[1] = 1 - meshData.uv_coords[loop.vert.index][1]

                                    mat = bpy.data.materials.new(name=name + "_material")
                                    obj.data.materials.append(mat)

                                    tex = bpy.data.textures.new(shape.name + "_tex", 'IMAGE')
                                    tex.type = 'IMAGE'

                                    img_file = Path(os.path.join(os.path.dirname(self.file.filename), meshData.material.diffs))
                                    altImageFile = Path(os.path.join(os.path.dirname(self.file.filename), os.path.basename(self.file.filename).replace(".mesh", "") + "_diffuse.dds"))

                                    if img_file.is_file():
                                        img_file.resolve()
                                        image = bpy.data.images.load(str(img_file))
                                        tex.image = image
                                    elif altImageFile.is_file():
                                        altImageFile.resolve()
                                        image = bpy.data.images.load(str(altImageFile))
                                        tex.image = image
                                    else:
                                        print("No Texture File was found.")

                                    slot = mat.texture_slots.add()
                                    slot.texture = tex
                                    slot.bump_method = 'BUMP_ORIGINAL'
                                    slot.mapping = 'FLAT'
                                    slot.mapping_x = 'X'
                                    slot.mapping_y = 'Y'
                                    slot.texture_coords = 'UV'
                                    slot.use = True
                                    slot.uv_layer = uv_layer.name

                                bm.to_mesh(mesh)
                            else:
                                print("ERROR ::: Invalid Object in Shape: " + str(meshData))
                    else:
                        print("ERROR ::: Invalid Object in World: " + str(shape))
            elif isinstance(node, pdx_data.PdxLocators):
                for locator in node.locators:
                    print("Locators")
                    #obj = bpy.data.objects.new(locator.name, None)
                    #bpy.context.scene.objects.link(obj)
                    #obj.empty_draw_size = 2
                    #obj.empty_draw_type = 'PLAIN_AXES'
                    #obj.location = mathutils.Vector((locator.pos[0], locator.pos[1], locator.pos[2])) * mat_rot
            else:
                print("ERROR ::: Invalid node found: " + str(node))