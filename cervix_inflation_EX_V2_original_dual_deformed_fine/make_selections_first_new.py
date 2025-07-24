import igl
import numpy as np
import meshio
import math

def make_selections(volumetric_mesh_fname, CX_fname):
 
    # Your existing code
    mm = meshio.read(volumetric_mesh_fname)
    v = mm.points
    # Rescale back by 1000
    v *= 1000
    t = mm.cells_dict["tetra"]
    f = igl.boundary_facets(t)
    c = igl.facet_components(f)
    tet_barycenters = np.mean(v[t, :], axis=1)
    triangle_barycenters = np.mean(v[f, :], axis=1)

    # At the cervix, find: min y and x at min y (x lower bound), max x (x upper bound) and y at max x
    mesh_ori_CX = meshio.read(CX_fname)
    pts_ori_CX = mesh_ori_CX.points   # shape (N,3)

    # Since CX is at the positive end of x, find its x-range
    cx_x_min = np.min(pts_ori_CX[:, 0])
    cx_x_max = np.max(pts_ori_CX[:, 0])

    print(f"CX mesh x-range: {cx_x_min:.3f} to {cx_x_max:.3f}")

    # Exclude the CX portion from volumetric mesh
    # Keep only points with x < cx_x_min (before the CX starts)
    volumetric_without_cx_mask = v[:, 0] < cx_x_min
    volumetric_without_cx = v[volumetric_without_cx_mask]

    if len(volumetric_without_cx) > 0:
        # Extract x coordinates excluding CX portion
        x_coords_without_cx = volumetric_without_cx[:, 0]
        
        # Find the range of x coordinates (excluding CX portion)
        x_min_without_cx = np.min(x_coords_without_cx)
        x_max_without_cx = np.max(x_coords_without_cx)
        x_range_without_cx = x_max_without_cx - x_min_without_cx
        
        # Find the 95th percentile (top 5%) of x coordinates
        x_95th_percentile = np.percentile(x_coords_without_cx, 95)
        # Store results for further use
        x_range = (x_min_without_cx, x_max_without_cx)
        top_5_percent_x = x_95th_percentile
    
    else:
        x_range = None
        top_5_percent_x = None

        # For comparison, show the full volumetric mesh stats
        all_x_coords = v[:, 0]

    dirichlet_selection = (triangle_barycenters[:, 0] > x_max_without_cx)

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

    # Identify surface indices for each type
    inner_surface_indices = np.where(c == 1)[0]
    dirichlet_surface_indices = np.where(dirichlet_selection)[0]
    outer_surface_indices = np.where((c == 0) & ~dirichlet_selection)[0]

    surface_1_vertices = np.unique(f[dirichlet_surface_indices].flatten()) if len(dirichlet_surface_indices) > 0 else np.array([])
    surface_2_vertices = np.unique(f[inner_surface_indices].flatten()) if len(inner_surface_indices) > 0 else np.array([])
    surface_3_vertices = np.unique(f[outer_surface_indices].flatten()) if len(outer_surface_indices) > 0 else np.array([])
    
    surface_1_count = len(surface_1_vertices)
    surface_2_count = len(surface_2_vertices) 
    surface_3_count = len(surface_3_vertices)
    
    print(f"Surface vertex counts - Dirichlet (1): {surface_1_count}, Inner (2): {surface_2_count}, Outer (3): {surface_3_count}")

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
    make_selections("LORIP45V2_UTCX_deformed_V2.msh", "LORIP45V2_CX.stl")
