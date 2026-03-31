


portuguese/
│
├── app/
│   ├── main.py                # CLI entry point
│   ├── pipeline.py            # main orchestration
│   ├── parser.py              # extract phrases from docx
│   ├── analyzer.py            # phrase → image prompt
│   ├── image_generator.py     # create images (placeholder for now)
│   ├── doc_builder.py         # build output docx
│   ├── models.py              # simple data classes
│   └── config.py              # paths/config
│
├── input/                     # teacher uploads go here (local testing)
├── output/                    # generated worksheets
├── images/                    # generated images
│
├── requirements.txt
└── README.md