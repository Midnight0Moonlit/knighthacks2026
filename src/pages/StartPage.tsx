import {useNavigate} from "react-router-dom";

export default function StartPage() {
    //Initialize the navigate function from react-router-dom to programmatically navigate between routes
    const navigate = useNavigate();

    return (
        <div className="page-wrapper">
            {/* The Top Bar*/}
            <header className="top-bar">
                <div className="project-name">
                    <strong>Budget Buddies</strong> • Powered by Jetson
                </div>
            </header>

            {/* The Main Content */}
            <main className="main-content">
                <h1 className="page-title">Welcome to Budget Buddies</h1>
                <h2>Ready to start your shopping trip?</h2>
            {/* Trigger navigation on click */}
            <button className="giant-start-btn" onClick={() => navigate('/budget')}> START ➔ </button>
            <p className="helper-text">Tap here to set your budget and begin.</p>
            
            </main>
        </div>
    )
}
