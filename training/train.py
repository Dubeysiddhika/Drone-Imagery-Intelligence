from ultralytics import YOLO

# Load a small pretrained YOLO model
model = YOLO("yolo11n.pt")

# Train on our VisDrone dataset
results = model.train(
    data=r"D:\Drone-image-intelligence\dataset\data.yaml",
    epochs=50,
    imgsz=640,
    batch=8,
    workers=4,
    project=r"D:\Drone-image-intelligence\runs",
    name="drone_person_vehicle"
)

print("Training completed.")
print("Best model should be saved inside:")
print(r"D:\Drone-image-intelligence\runs\drone_person_vehicle\weights\best.pt")