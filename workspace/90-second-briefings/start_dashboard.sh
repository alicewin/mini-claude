#!/bin/bash
# Quick start script for 90-Second Briefings Dashboard

echo "🚀 Starting 90-Second Briefings Dashboard..."

# Check if streamlit is installed
if ! python3 -c "import streamlit" 2>/dev/null; then
    echo "📦 Installing Streamlit..."
    pip3 install streamlit pandas
fi

# Check if dashboard is already running
if curl -s http://localhost:8000 > /dev/null; then
    echo "✅ Dashboard already running at http://localhost:8000"
else
    echo "🖥️  Starting dashboard..."
    
    # Start the dashboard
    echo "" | python3 -m streamlit run dashboard/app.py --server.port=8000 --server.address=0.0.0.0 > streamlit.log 2>&1 &
    
    # Wait for it to start
    echo "⏳ Waiting for dashboard to start..."
    sleep 5
    
    # Check if it's running
    if curl -s http://localhost:8000 > /dev/null; then
        echo "✅ Dashboard started successfully!"
        echo "🌐 Access it at: http://localhost:8000"
        echo "📊 View your demo briefings in the 'Latest Briefings' tab"
        echo "📝 Log file: streamlit.log"
    else
        echo "❌ Failed to start dashboard. Check streamlit.log for errors."
    fi
fi

echo ""
echo "📋 Available demo briefings:"
ls -la data/briefing_*.md 2>/dev/null | tail -5 || echo "No briefings found. Run: python3 scripts/demo.py --all"
echo ""
echo "🛑 To stop: pkill -f streamlit"