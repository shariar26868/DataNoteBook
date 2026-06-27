import { createSlice, createAsyncThunk, PayloadAction } from "@reduxjs/toolkit";
import { fetchStorageLocationsAction, createProjectAction, createFolderAction, fetchProjectsAction } from "@/lib/actions/project.action";

export interface StorageLocation {
  id: string;
  name: string;
}

export interface ProjectData {
  id: string;
  name: string;
  storage_location: string | any;
  created_at?: string;
  updated_at?: string;
  company?: string;
}

export interface ProjectState {
  storageLocations: StorageLocation[];
  locationsLoading: boolean;
  createProjectLoading: boolean;
  createFolderLoading: boolean;
  error: string | null;
  selectedLocation: string;
  projects: ProjectData[];
  projectsLoading: boolean;
}

const initialState: ProjectState = {
  storageLocations: [],
  locationsLoading: false,
  createProjectLoading: false,
  createFolderLoading: false,
  error: null,
  selectedLocation: "",
  projects: [],
  projectsLoading: false,
};

export const fetchStorageLocations = createAsyncThunk(
  "project/fetchStorageLocations",
  async (_, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem("token");
      const result = await fetchStorageLocationsAction(token);
      if (!result.success) {
        throw new Error(result.error || "Failed to fetch storage locations");
      }
      const data = result.data;
      if (data.success && Array.isArray(data.data)) {
        return data.data as StorageLocation[];
      }
      return rejectWithValue("Invalid response structure for storage locations");
    } catch (err: any) {
      return rejectWithValue(err.message || "Failed to fetch storage locations");
    }
  }
);

export const createProject = createAsyncThunk(
  "project/createProject",
  async ({ name, storageLocation }: { name: string; storageLocation: string }, { rejectWithValue }) => {
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const result = await createProjectAction(name, storageLocation, token);
      if (!result.success) {
        throw new Error(result.error || "Failed to create project");
      }
      return result.data;
    } catch (err: any) {
      return rejectWithValue(err.message || "Failed to create project");
    }
  }
);

export const createFolder = createAsyncThunk(
  "project/createFolder",
  async ({ name, projectId }: { name: string; projectId: string }, { rejectWithValue }) => {
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const result = await createFolderAction(name, projectId, token);
      if (!result.success) {
        throw new Error(result.error || "Failed to create folder");
      }
      return result.data;
    } catch (err: any) {
      return rejectWithValue(err.message || "Failed to create folder");
    }
  }
);

export const fetchProjects = createAsyncThunk(
  "project/fetchProjects",
  async (_, { rejectWithValue }) => {
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const result = await fetchProjectsAction(token);
      if (!result.success) {
        throw new Error(result.error || "Failed to fetch projects");
      }
      const data = result.data;
      if (data && data.success && Array.isArray(data.data)) {
        return data.data as ProjectData[];
      }
      if (Array.isArray(data)) {
        return data as ProjectData[];
      }
      return rejectWithValue("Invalid projects data format");
    } catch (err: any) {
      return rejectWithValue(err.message || "Failed to fetch projects");
    }
  }
);

const projectSlice = createSlice({
  name: "project",
  initialState,
  reducers: {
    setSelectedLocation: (state, action: PayloadAction<string>) => {
      state.selectedLocation = action.payload;
    },
    clearProjectError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch Storage Locations
      .addCase(fetchStorageLocations.pending, (state) => {
        state.locationsLoading = true;
        state.error = null;
      })
      .addCase(fetchStorageLocations.fulfilled, (state, action: PayloadAction<StorageLocation[]>) => {
        state.locationsLoading = false;
        state.storageLocations = action.payload;
        if (action.payload.length > 0) {
          state.selectedLocation = action.payload[0].id;
        }
      })
      .addCase(fetchStorageLocations.rejected, (state, action) => {
        state.locationsLoading = false;
        state.error = (action.payload as string) || "Could not fetch storage locations";
      })
      // Create Project
      .addCase(createProject.pending, (state) => {
        state.createProjectLoading = true;
        state.error = null;
      })
      .addCase(createProject.fulfilled, (state) => {
        state.createProjectLoading = false;
      })
      .addCase(createProject.rejected, (state, action) => {
        state.createProjectLoading = false;
        state.error = (action.payload as string) || "Could not create project";
      })
      // Create Folder
      .addCase(createFolder.pending, (state) => {
        state.createFolderLoading = true;
        state.error = null;
      })
      .addCase(createFolder.fulfilled, (state) => {
        state.createFolderLoading = false;
      })
      .addCase(createFolder.rejected, (state, action) => {
        state.createFolderLoading = false;
        state.error = (action.payload as string) || "Could not create folder";
      })
      // Fetch Projects
      .addCase(fetchProjects.pending, (state) => {
        state.projectsLoading = true;
        state.error = null;
      })
      .addCase(fetchProjects.fulfilled, (state, action: PayloadAction<ProjectData[]>) => {
        state.projectsLoading = false;
        state.projects = action.payload;
      })
      .addCase(fetchProjects.rejected, (state, action) => {
        state.projectsLoading = false;
        state.error = (action.payload as string) || "Could not fetch projects";
      });
  },
});

export const { setSelectedLocation, clearProjectError } = projectSlice.actions;
export default projectSlice.reducer;
