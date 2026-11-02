# Sia Live2D P0 prototype

The default page is the safe stage based on the setting-faithful adult
half-body `frontend/public/avatars/stage-realistic-night.png`.

The v10 00018 multi-view crop remains a structural reference only. It does not
match the novel's adult, millennium-traveler, flower-shop identity closely
enough to be the default character source.

Run from the repository root:

```powershell
python -m http.server 8765
```

Safe stage:

```text
http://127.0.0.1:8765/prototypes/live2d-p0/
```

Experimental face-layer separation:

```text
http://127.0.0.1:8765/prototypes/live2d-p0/face-redraw.html
```

The face-redraw experiment is not a production Live2D model and is no longer
the default entry.
