# Functional and Non-functional Requirements

The following are the functional and non-functional requirements of the system that are expected to perform and focus on users' expectation.

## Functional Requirements

1. The system must be able to identify common diseases affecting banana crops from aerial input images captured through a wireless drone or phone mirror feed.
2. The system must be able to classify healthy and diseased banana plants (Black Sigatoka, Bunchy Top, Panama disease, and healthy) and evaluate detection performance using validation metrics such as precision, recall, and mAP.
3. The system must provide geo-tagged disease information, field health summaries, and exported reports (JSON, CSV, and interactive map) to farmers and stakeholders for monitoring plantation conditions and supporting harvest planning.
4. The system must be able to preprocess captured images, generate vegetation stress indicators, and support model retraining from newly labeled datasets to improve disease detection over time.

## Non-functional Requirements

1. The system must be easy to use and intuitive for farmers and other stakeholders with limited technical expertise through a single desktop dashboard with live feed, detection overlays, and one-click field report export.
2. The system must be able to operate in offline mode for live capture, inference, and report export, with optional online connectivity for map basemap tiles and GPS auto-detection.
3. The system must be compatible with Windows desktop computers and support Android devices as a wireless mirror source for aerial video capture via scrcpy.
4. The system must be reliable and maintainable, with automated smoke testing, modular pipeline architecture, and a low risk of errors and downtime during field sessions.
