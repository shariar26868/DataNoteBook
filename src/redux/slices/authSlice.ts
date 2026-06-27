import { createSlice, createAsyncThunk, PayloadAction } from "@reduxjs/toolkit";

export interface Company {
  id: string;
  name: string;
}

export interface User {
  id: string;
  email: string;
  role: string;
  first_name: string | null;
  last_name: string | null;
  company: Company;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  error: string | null;
  isAuthenticated: boolean;
}

const getInitialState = (): AuthState => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token");
    const userStr = localStorage.getItem("user");
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr);
        return {
          user,
          token,
          isLoading: false,
          error: null,
          isAuthenticated: true,
        };
      } catch {
        // Clear corrupt storage
        localStorage.removeItem("token");
        localStorage.removeItem("user");
      }
    }
  }
  return {
    user: null,
    token: null,
    isLoading: false,
    error: null,
    isAuthenticated: false,
  };
};

const initialState: AuthState = getInitialState();

export const loginUser = createAsyncThunk(
  "auth/loginUser",
  async (credentials: { email: string; password: string }, { rejectWithValue }) => {
    try {
      const response = await fetch("https://qual-be.hcloud.q2labs.ai/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(credentials),
      });

      const data = await response.json();

      if (!response.ok) {
        let errorMsg = "Login failed";
        if (data) {
          if (typeof data.message === "string") {
            errorMsg = data.message;
          } else if (data.message && typeof data.message === "object" && data.message.message) {
            errorMsg = data.message.message;
          } else if (typeof data.error === "string") {
            errorMsg = data.error;
          } else if (data.error && typeof data.error === "object" && data.error.message) {
            errorMsg = data.error.message;
          } else if (typeof data.detail === "string") {
            errorMsg = data.detail;
          } else {
            errorMsg = JSON.stringify(data);
          }
        }
        return rejectWithValue(errorMsg);
      }

      if (data.success && data.data) {
        const { user, token } = data.data;
        if (typeof window !== "undefined") {
          localStorage.setItem("token", token);
          localStorage.setItem("user", JSON.stringify(user));
          localStorage.setItem("isLoggedIn", "true");
        }
        return { user, token };
      } else {
        let errorMsg = "Invalid response structure";
        if (data) {
          if (typeof data.message === "string") {
            errorMsg = data.message;
          } else if (data.message && typeof data.message === "object" && data.message.message) {
            errorMsg = data.message.message;
          }
        }
        return rejectWithValue(errorMsg);
      }
    } catch (err: any) {
      return rejectWithValue(err.message || "Network error occurred");
    }
  }
);

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    logout: (state) => {
      state.user = null;
      state.token = null;
      state.isAuthenticated = false;
      state.error = null;
      if (typeof window !== "undefined") {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        localStorage.removeItem("isLoggedIn");
        localStorage.removeItem("createdProjectId");
        localStorage.removeItem("createdFolderId");
      }
    },
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loginUser.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(loginUser.fulfilled, (state, action: PayloadAction<{ user: User; token: string }>) => {
        state.isLoading = false;
        state.isAuthenticated = true;
        state.user = action.payload.user;
        state.token = action.payload.token;
      })
      .addCase(loginUser.rejected, (state, action) => {
        state.isLoading = false;
        if (action.payload) {
          state.error = typeof action.payload === "string"
            ? action.payload
            : (action.payload as any).message || (action.payload as any).error || JSON.stringify(action.payload);
        } else {
          state.error = action.error?.message || "Something went wrong";
        }
        state.isAuthenticated = false;
      });
  },
});

export const { logout, clearError } = authSlice.actions;
export default authSlice.reducer;
