import { Cloud, Plus, X } from "lucide-react";
import { useState } from "react";

export default function Upload() {
  const [files, setFiles] = useState<File[]>([]);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files);
    setFiles([...files, ...droppedFiles]);
  };

  return (
    <div className="page-content">
      <div className="page-header">
        <div>
          <h1>Upload Imagery</h1>
          <p>Upload drone imagery for analysis and processing.</p>
        </div>
      </div>

      <div className="card">
        <div
          className="upload-zone"
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
        >
          <div className="upload-icon">
            <Cloud size={36} />
          </div>
          <h3>Drop images here to upload</h3>
          <p>or click to browse your computer</p>
          <input type="file" multiple hidden accept="image/*" />
        </div>
      </div>

      {files.length > 0 && (
        <div className="section" style={{ marginTop: "24px" }}>
          <div className="section-header">
            <h2>Uploaded Files ({files.length})</h2>
          </div>
          <div className="image-grid">
            {files.map((file, i) => (
              <div key={i} className="image-card">
                <div className="image-placeholder" />
                <div className="image-info">
                  <div className="image-name">{file.name}</div>
                  <div className="image-meta">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}