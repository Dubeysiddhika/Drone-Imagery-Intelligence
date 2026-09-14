export default function Settings() {
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-description">
            Manage your platform preferences.
          </p>
        </div>
      </div>

      <div className="card settings-card">
        <h3>Profile Information</h3>

        <label>Name</label>
        <input value="Siddhika" readOnly />

        <label>Email</label>
        <input value="researcher@example.com" readOnly />

        <label>Role</label>
        <input value="Researcher" readOnly />

        <button className="primary-button">
          Save Changes
        </button>
      </div>
    </div>
  );
}