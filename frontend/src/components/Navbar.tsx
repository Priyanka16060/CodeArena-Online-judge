import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <header className="topbar">
      <div className="brand">
        CodeArena <small>Case Files</small>
      </div>
      <nav className="nav-links">
        {user && (
          <>
            <NavLink to="/problems" className={({ isActive }) => (isActive ? "active" : "")}>
              Problems
            </NavLink>
            <NavLink to="/submissions" className={({ isActive }) => (isActive ? "active" : "")}>
              My Submissions
            </NavLink>
            <span className="folder-tab">{user.username}</span>
            <button onClick={handleLogout}>Sign out</button>
          </>
        )}
        {!user && (
          <>
            <NavLink to="/login">Sign in</NavLink>
            <NavLink to="/register">Register</NavLink>
          </>
        )}
      </nav>
    </header>
  );
}
