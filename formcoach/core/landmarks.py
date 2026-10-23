"""MediaPipe Pose landmark indices and skeleton connections."""
from __future__ import annotations

NOSE = 0
LEFT_EYE, RIGHT_EYE = 2, 5
LEFT_EAR, RIGHT_EAR = 7, 8
LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12
LEFT_ELBOW, RIGHT_ELBOW = 13, 14
LEFT_WRIST, RIGHT_WRIST = 15, 16
LEFT_HIP, RIGHT_HIP = 23, 24
LEFT_KNEE, RIGHT_KNEE = 25, 26
LEFT_ANKLE, RIGHT_ANKLE = 27, 28
LEFT_HEEL, RIGHT_HEEL = 29, 30
LEFT_FOOT, RIGHT_FOOT = 31, 32  # foot index (toes)

NUM_LANDMARKS = 33

# Per-side joint lookup so exercises can be written once for "the visible side".
SIDE = {
    "left": {
        "shoulder": LEFT_SHOULDER, "elbow": LEFT_ELBOW, "wrist": LEFT_WRIST,
        "hip": LEFT_HIP, "knee": LEFT_KNEE, "ankle": LEFT_ANKLE,
        "heel": LEFT_HEEL, "foot": LEFT_FOOT, "ear": LEFT_EAR,
    },
    "right": {
        "shoulder": RIGHT_SHOULDER, "elbow": RIGHT_ELBOW, "wrist": RIGHT_WRIST,
        "hip": RIGHT_HIP, "knee": RIGHT_KNEE, "ankle": RIGHT_ANKLE,
        "heel": RIGHT_HEEL, "foot": RIGHT_FOOT, "ear": RIGHT_EAR,
    },
}

# Body connections drawn by the overlay (face mesh points are skipped on purpose).
CONNECTIONS = [
    (LEFT_SHOULDER, RIGHT_SHOULDER), (LEFT_HIP, RIGHT_HIP),
    (LEFT_SHOULDER, LEFT_HIP), (RIGHT_SHOULDER, RIGHT_HIP),
    (LEFT_SHOULDER, LEFT_ELBOW), (LEFT_ELBOW, LEFT_WRIST),
    (RIGHT_SHOULDER, RIGHT_ELBOW), (RIGHT_ELBOW, RIGHT_WRIST),
    (LEFT_HIP, LEFT_KNEE), (LEFT_KNEE, LEFT_ANKLE),
    (RIGHT_HIP, RIGHT_KNEE), (RIGHT_KNEE, RIGHT_ANKLE),
    (LEFT_ANKLE, LEFT_HEEL), (LEFT_HEEL, LEFT_FOOT), (LEFT_ANKLE, LEFT_FOOT),
    (RIGHT_ANKLE, RIGHT_HEEL), (RIGHT_HEEL, RIGHT_FOOT), (RIGHT_ANKLE, RIGHT_FOOT),
]
BODY_POINTS = sorted({i for c in CONNECTIONS for i in c} | {NOSE})
