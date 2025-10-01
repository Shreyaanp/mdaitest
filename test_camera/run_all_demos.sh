#!/bin/bash
# Run all design demos - Identity of Soul Scanner Gallery

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     IDENTITY OF SOUL - SCANNER DESIGN GALLERY 🎨              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Choose a design to preview:"
echo ""
echo "  1. 🧘 Minimalist Zen       - Pure black, pulsing dot, ripples"
echo "  2. 🌃 Cyberpunk Neon       - Pink/cyan, glitch art, HUD"
echo "  3. 𓂀 Ancient Egyptian     - Hieroglyphs, gold, Eye of Ra"
echo "  4. 💚 Matrix Code Rain     - Falling characters, void orb"
echo "  5. ✨ Particle Field       - Gathering particles, ethereal"
echo "  6. 🌅 Synthwave Retro      - Grid floor, sunset, 80s vibe"
echo "  7. ⬡ Sacred Geometry       - Flower of Life, kaleidoscope"
echo "  8. 🎵 Sound Visualizer     - Circular spectrum, waveforms"
echo "  9. 🎮 90s Terminal (original) - Green scanlines, retro UI"
echo ""
echo "  0. Exit"
echo ""
read -p "Enter choice (0-9): " choice

case $choice in
    1)
        echo "Launching Zen Scanner..."
        python design_1_zen.py
        ;;
    2)
        echo "Launching Cyberpunk Scanner..."
        python design_2_cyberpunk.py
        ;;
    3)
        echo "Launching Egyptian Scanner..."
        python design_3_egyptian.py
        ;;
    4)
        echo "Launching Matrix Scanner..."
        python design_4_matrix.py
        ;;
    5)
        echo "Launching Particle Scanner..."
        python design_5_particles.py
        ;;
    6)
        echo "Launching Synthwave Scanner..."
        python design_6_synthwave.py
        ;;
    7)
        echo "Launching Geometric Scanner..."
        python design_7_geometric.py
        ;;
    8)
        echo "Launching Soundwave Scanner..."
        python design_8_soundwave.py
        ;;
    9)
        echo "Launching 90s Terminal Scanner..."
        python retro_scanner.py
        ;;
    0)
        echo "Goodbye!"
        exit 0
        ;;
    *)
        echo "Invalid choice!"
        ;;
esac




