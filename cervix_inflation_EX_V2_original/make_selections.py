import igl
import numpy as np
import meshio
import math

def make_selections(volumetric_mesh_fname, CX_fname):
    coverage_percent = 0.5
    mm = meshio.read(volumetric_mesh_fname)
    v = mm.points
    t = mm.cells_dict["tetra"]
    f = igl.boundary_facets(t)
    c = igl.facet_components(f)
    tet_barycenters = np.mean(v[t, :], axis=1)
    triangle_barycenters = np.mean(v[f, :], axis=1)
    
    # Load cervix mesh
    mesh_ori_CX = meshio.read(CX_fname)
    pts_ori_CX = mesh_ori_CX.points
    idx_max_x_ori_CX = np.argmax(pts_ori_CX[:, 0])
    idx_min_y_ori_CX = np.argmin(pts_ori_CX[:, 1])
    p1_ori_CX = pts_ori_CX[idx_max_x_ori_CX]
    p2_ori_CX = pts_ori_CX[idx_min_y_ori_CX]
    
    max_x = p1_ori_CX[0]
    min_x_cx = np.min(pts_ori_CX[:, 0])
    total_length_x = max_x - min_x_cx
    
    # Calculate coverage boundary
    coverage_length = coverage_percent * total_length_x
    coverage_boundary = max_x - coverage_length
    
    # Simple geometric selection
    y_center = (np.max(pts_ori_CX[:, 1]) + np.min(pts_ori_CX[:, 1])) / 2
    y_range = np.max(pts_ori_CX[:, 1]) - np.min(pts_ori_CX[:, 1])
    y_tolerance = 0.6 * y_range
    
    dirichlet_selection = (triangle_barycenters[:, 0] >= coverage_boundary) & \
                         (triangle_barycenters[:, 0] <= max_x) & \
                         (np.abs(triangle_barycenters[:, 1] - y_center) <= y_tolerance)
    
    print(f"Selected {np.sum(dirichlet_selection)} triangles for Dirichlet BC")

    with open("surface_selections.txt", "w") as file_:
        # Select inner surface and label as 2
        for i, j, k in f[c == 1]:
            file_.write(f"2 {i} {j} {k}\n")

        # Write dirichlet boundary as 1
        for idx in np.where(dirichlet_selection)[0]:  
            i, j, k = f[idx]
            file_.write(f"1 {i} {j} {k}\n")
        
        # Select outer surface and label as 3 (excluding Dirichlet)
        outer_surface_indices = np.where((c == 0) & ~dirichlet_selection)[0] 
        for idx in outer_surface_indices:
            i, j, k = f[idx]
            file_.write(f"3 {i} {j} {k}\n")

    CX = meshio.read(CX_fname)

    with open("volume_selections.txt", "w") as file_:
        # Calculate winding number to determine if points are inside CX
        w1 = igl.winding_number(CX.points.astype(np.double), CX.cells_dict["triangle"], tet_barycenters)
        
        # Initialize all tetrahedra as UT (ID 2)
        volume_selections = np.ones(t.shape[0], dtype=int) * 2
        
        # Tetrahedra inside CX get ID 1
        volume_selections[w1 > 0.5] = 1

        print("CX volume gets volume id 1")
        print("UT volume (everything else) gets volume id 2")
        print(f"Found {(volume_selections == 1).sum()} tetrahedra inside CX")
        print(f"Found {(volume_selections == 2).sum()} tetrahedra outside CX (in UT)")

        # Write volume IDs to file
        for i in volume_selections:
            file_.write(f"{i}\n")

if __name__ == "__main__":
    make_selections("LORIP45V2_UTCX.msh", "LORIP45V2_CX.stl")
