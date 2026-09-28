async function login() {
    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;
    const loginMessage = document.getElementById("loginMessage");

    try {
        const formData = new URLSearchParams();

        formData.append("username", username);
        formData.append("password", password);

        const response = await fetch(
            "http://127.0.0.1:8000/auth/login",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                body: formData
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Login failed");
        }

        localStorage.setItem(
            "bugflow_token",
            data.access_token
        );

        loginMessage.textContent = "Login successful!";
        loginMessage.className = "success";

        loadDashboard();

    } catch (error) {
        console.error(error);

        loginMessage.textContent =
            "Login failed: " + error.message;

        loginMessage.className = "error";
    }
}


async function loadDashboard() {

    const token = localStorage.getItem("bugflow_token");

    if (!token) {
        showLogin();
        return;
    }

    const statusContainer =
        document.getElementById("statusContainer");

    const systemStatus =
        document.getElementById("systemStatus");

    try {

        const headers = {
            "Authorization": `Bearer ${token}`
        };

        // Admin Dashboard
        const dashboardResponse = await fetch(
            "http://127.0.0.1:8000/admin/dashboard",
            {
                headers: headers
            }
        );

        if (!dashboardResponse.ok) {

            if (dashboardResponse.status === 401 ||
                dashboardResponse.status === 403) {

                localStorage.removeItem("bugflow_token");
                showLogin();
                return;
            }

            throw new Error("Dashboard API failed");
        }

        const dashboardData =
            await dashboardResponse.json();

        document.getElementById("totalIssues").textContent =
            dashboardData.total_issues;

        document.getElementById("totalUsers").textContent =
            dashboardData.total_users;

        document.getElementById("totalSprints").textContent =
            dashboardData.total_sprints;


        // Issue Analytics
        const analyticsResponse = await fetch(
            "http://127.0.0.1:8000/analytics/issues",
            {
                headers: headers
            }
        );

        if (!analyticsResponse.ok) {
            throw new Error("Analytics API failed");
        }

        const analyticsData =
            await analyticsResponse.json();

        statusContainer.innerHTML = "";

        Object.entries(
            analyticsData.issues_by_status
        ).forEach(([status, count]) => {

            const statusCard =
                document.createElement("div");

            statusCard.className = "status";

            statusCard.innerHTML = `
                ${status}
                <strong>${count}</strong>
            `;

            statusContainer.appendChild(statusCard);
        });


        systemStatus.textContent =
            "BugFlow API is running successfully";

        systemStatus.className = "";

    } catch (error) {

        console.error(error);

        statusContainer.innerHTML =
            '<p class="error">Unable to load analytics data.</p>';

        systemStatus.textContent =
            "Unable to connect to BugFlow API";

        systemStatus.className = "error";
    }
}


function showLogin() {

    const container =
        document.querySelector(".container");

    const existing =
        document.getElementById("loginBox");

    if (existing) {
        return;
    }

    const loginBox =
        document.createElement("section");

    loginBox.id = "loginBox";
    loginBox.className = "section";

    loginBox.innerHTML = `
        <h2>Admin Login</h2>

        <input
            id="username"
            type="text"
            placeholder="Username"
            style="
                width:100%;
                padding:12px;
                margin:10px 0;
            "
        >

        <input
            id="password"
            type="password"
            placeholder="Password"
            style="
                width:100%;
                padding:12px;
                margin:10px 0;
            "
        >

        <button
            onclick="login()"
            style="
                padding:12px 20px;
                background:#1f2937;
                color:white;
                border:none;
                border-radius:6px;
                cursor:pointer;
            "
        >
            Login
        </button>

        <p id="loginMessage" style="margin-top:15px;"></p>
    `;

    container.insertBefore(
        loginBox,
        container.firstChild
    );
}


loadDashboard();