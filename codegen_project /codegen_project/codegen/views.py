import json, os, traceback, re, openai
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST, require_GET
from django.shortcuts import render
from dotenv import load_dotenv
from .models import ProjectHistory
from .utils.load_requirements import load_security_checks, get_save_base_path
from .utils.helpers import extract_json_array, process_file_content
from pathlib import Path

load_dotenv()
# Fetch the OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is missing in the .env file!")

# Load security checks from JSON file
def load_security_checks():
    try:
        with open("security_checks.json", "r") as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading security checks: {e}")
        # Default values if file can't be loaded
        return {
            "security": [
                "Sanitize user input to prevent injection attacks.",
                "Implement API rate limiting.",
                "Use authentication and authorization mechanisms.",
                "Validate and sanitize data before processing.",
                "Handle exceptions properly to avoid exposing sensitive information."
            ],
            "error_classes": [
                "ValidationError",
                "PermissionDenied", 
                "SyntaxError",
                "RuntimeError"
            ]
        }


framework_requirements_map = {
    "django": "- For Django: include a `core` app with models.py, views.py, urls.py, apps.py, and register it in settings.py > INSTALLED_APPS.",
    "express": "- For Express.js: include `server.js`, route files, middleware, and `package.json`.",
    "node": "- For native Node.js (without Express): use the built-in `http` module. Include `server.js`, route handler modules, and `package.json`.",
    "react": "- For React: use a `public/` and `src/` folder structure with `App.js` and `index.js` as entry points.",
    "flask": "- For Flask: include `app.py`, `routes.py`, and `requirements.txt`. Use Blueprints if modular.",
    "php": "- For PHP: include `index.php`, `config.php`, and `composer.json`.",
    "go": "- For Go: include `main.go`, `go.mod`, and use idiomatic structuring for routing and services.",
    "spring": "- For Spring Boot: include `Main.java`, `pom.xml`, and `application.properties`.",
    "nextjs": "- For Next.js: include `pages/`, `public/`, and `package.json`.",
}

# Updated system prompt for generating complete projects
UNIVERSAL_SYSTEM_PROMPT = """
You are an expert Secure Code Generator AI. Generate a complete, production-ready {language} project based on this user request:

"{user_request}"

Use idiomatic {language} practices and the standard project layout for the selected framework.

The project must include:
- Secure authentication (if Web or API).
- Complete input validation and structured error handling.
- Dependency management (e.g., requirements.txt, package.json).
- All required configuration and environment setup.
- Code that works out of the box for both local development and deployment.

IMPORTANT RULES:
- For any file you are updating or creating, include the ENTIRE content of that file — not just the new or modified part.
- NEVER return partial file contents.
- DO NOT return empty or placeholder files. Every file MUST contain working, relevant code.
- NO markdown formatting, explanations, or placeholder comments.
- DO NOT mix code from other languages or frameworks.
- Use ONLY the language specified: {language}
- Use ONLY the selected framework: {framework} ({framework_version})
- Use ONLY the specified database: {database}
- Use ONLY the specified testing framework: {testing_framework}
- Do NOT include any files, packages, code, or libraries unrelated to the selected stack.
- Do NOT include placeholder or empty files.
- Do NOT assume defaults or auto-switch technologies.

Dependency & Package Management:
- Include all required packages for the selected stack.
- For Python: add them to `requirements.txt`
- For Node.js: add them to `package.json`
- For Java: add them to `pom.xml` or `build.gradle`
- For PHP: add them to `composer.json`
- For Go: use `go.mod`

All dependencies MUST be:
- Required for the selected language + framework
- Declared explicitly in the setup files
- Reflecting the correct versions where applicable

Violations will result in project rejection. Stick strictly to the chosen tech stack.

Mandatory Project Metadata:
1. Project Name: {project_name}
2. Project Description: {project_description}
3. Project Type: {project_type}
4. Framework : {framework}
5. Framework Version : {framework_version}
6. Project Architecture: {architecture}
7. Database Type: {database}
8. Testing Framework: {testing_framework}
9. Authentication Method: {authentication_method}

Optional (Recommended):
10. Deployment Target: {deployment_target}
11. CI/CD Integration: {ci_cd_integration}
12. API Documentation: {api_documentation}
13. Initial Modules: {initial_modules}
14. Environment Management: {env_management}

Security & Best Practices (From security_check.json):
- Prevent SQL Injection, XSS, CSRF.
- Use parameterized queries or ORM.
- Sanitize all input/output.
- Enable CSRF protection for state-changing operations.
- Implement secure authentication (JWT, OAuth2, API Keys, etc.).
- Encrypt sensitive data. Enforce HTTPS.
- Avoid hardcoded secrets or debug modes in production.
- Apply error handling with: ValidationError, PermissionDenied, SyntaxError, RuntimeError.

Logging:
- Include logging (with timestamps and error tracebacks).
- Logging should differ between dev and prod.

{framework_requirements}
"""


# Function to install dependencies based on the language
def install_dependencies(project_path, language):
    try:
        if language == "python" and os.path.exists(os.path.join(project_path, "requirements.txt")):
            subprocess.run(["pip", "install", "-r", "requirements.txt"], cwd=project_path, check=True)

        elif language in ["javascript", "nodejs"] and os.path.exists(os.path.join(project_path, "package.json")):
            subprocess.run(["npm", "install"], cwd=project_path, check=True)

        elif language == "java" and os.path.exists(os.path.join(project_path, "pom.xml")):
            subprocess.run(["mvn", "install"], cwd=project_path, check=True)

        elif language == "php" and os.path.exists(os.path.join(project_path, "composer.json")):
            subprocess.run(["composer", "install"], cwd=project_path, check=True)

        elif language == "go" and os.path.exists(os.path.join(project_path, "go.mod")):
            subprocess.run(["go", "mod", "tidy"], cwd=project_path, check=True)

        elif language == "ruby" and os.path.exists(os.path.join(project_path, "Gemfile")):
            subprocess.run(["bundle", "install"], cwd=project_path, check=True)

        elif language == "rust" and os.path.exists(os.path.join(project_path, "Cargo.toml")):
            subprocess.run(["cargo", "build"], cwd=project_path, check=True)

        elif language == "csharp" and os.path.exists(os.path.join(project_path, "*.csproj")):
            subprocess.run(["dotnet", "restore"], cwd=project_path, check=True)

        elif language == "kotlin" and os.path.exists(os.path.join(project_path, "build.gradle")):
            subprocess.run(["./gradlew", "build"], cwd=project_path, check=True)

        print(f" Dependencies installed for {language}")
    except subprocess.CalledProcessError as e:
        print(f" Dependency installation failed for {language}: {str(e)}")


# Fixed extract_json_array function
def extract_json_array(text):
    """Extract a JSON array from text using multiple strategies with improved error handling"""
    
    
    try:
        # Clean the text before any processing
        cleaned_text = text.strip()
        # Remove markdown formatting
        cleaned_text = re.sub(r'```(?:python|json)?\s*', '', cleaned_text)
        cleaned_text = re.sub(r'```\s*$', '', cleaned_text)

        # Escape problematic control characters
        cleaned_text = re.sub(r'(?<!\\)\\n', r'\\n', cleaned_text)
        cleaned_text = re.sub(r'(?<!\\)\\t', r'\\t', cleaned_text)
        cleaned_text = re.sub(r'(?<!\\)\\r', r'\\r', cleaned_text)

        # Try direct JSON parsing first
        try:
            parsed_json = json.loads(cleaned_text)
            if isinstance(parsed_json, list):
                # Validate structure before returning
                for item in parsed_json:
                    if not isinstance(item, dict) or 'filename' not in item or 'content' not in item:
                        print(f"Invalid item structure: {item}")
                        continue
                return parsed_json
            elif isinstance(parsed_json, dict) and 'files' in parsed_json:
                return parsed_json['files']
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
        
        # Try finding a JSON array pattern with regex
        json_pattern = r'\[\s*\{[\s\S]*?\}\s*\]'
        json_match = re.search(json_pattern, cleaned_text, re.DOTALL)
        
        if json_match:
            try:
                potential_json = json_match.group(0)
                # Further clean up the extracted JSON string
                potential_json = re.sub(r'\\\\+', r'\\', potential_json)  # Fix double backslashes safely
                parsed_json = json.loads(potential_json)
                return parsed_json
            except json.JSONDecodeError as e:
                print(f"JSON parse error in regex match: {e}")
        
        # Fallback: Try to extract file objects manually
        file_objects = []
        file_pattern = r'\{\s*"filename"\s*:\s*"([^"]+)"\s*,\s*"content"\s*:\s*"([\s\S]*?)"\s*\}'
        matches = re.findall(file_pattern, cleaned_text)
        
        if matches:
            for filename, content in matches:
                file_objects.append({
                    "filename": filename,
                    "content": content
                })
            if file_objects:
                return file_objects
     
    except Exception as e:
        print(f"Error in extract_json_array: {str(e)}")
    
    # Fallback: create a simple text file with the response
    return [{"filename": "response.txt", "content": text}]
    
    # Fallback: create a simple text file with the response
    return [{"filename": "response.txt", "content": text}]

# Fixed process_file_content function

def process_file_content(files):
    """Process file content with improved validation, path correction, and sanitization."""
    processed_files = []

    if not files or not isinstance(files, list):
        print("Invalid files input:", files)
        return [{"filename": "error.txt", "content": "No valid files data received"}]

    for file in files:
        try:
            if not isinstance(file, dict):
                print(f"Invalid file object (not a dict): {type(file)}")
                continue

            filename = file.get('filename')
            content = file.get('content')

            if not filename:
                print("Missing filename in file object")
                filename = "unnamed_file.txt"

            if not isinstance(content, str):
                print(f"Invalid content type for {filename}: {type(content)}")
                content = str(content)

            # Step 1: Clean the filename
            filename = filename.replace("\\", "/")  # Normalize slashes
            filename = re.sub(r'[^\w/\.-]', '_', filename)  # Remove unsafe characters

            # Step 2: Handle flattened paths like "core_models.py"
            if "_" in filename and not "/" in filename and filename.endswith(".py"):
                parts = filename.split("_")
                if len(parts) > 1:
                    filename = os.path.join(parts[0], "_".join(parts[1:]))

            # Step 3: Sanitize content
            clean_content = content.strip()

            # Remove triple-quoted strings (if they wrap the whole thing)
            clean_content = re.sub(r'^(["\']{3})(.*?)(["\']{3})$', r'\2', clean_content, flags=re.DOTALL)

            # Remove markdown code block markers
            clean_content = re.sub(r'^```[\w]*\n?', '', clean_content)
            clean_content = re.sub(r'\n?```$', '', clean_content)

            # Unescape escaped quotes
            clean_content = clean_content.replace('\\"', '"').replace("\\'", "'")

            processed_files.append({
                "filename": filename,
                "content": clean_content
            })
        except Exception as e:
            print(f"Error processing file: {str(e)}")

    return processed_files if processed_files else [{"filename": "empty.txt", "content": "No valid files found"}]


def merge_or_append(file_path, new_content):
    """Merge or append new content to an existing file.This function checks if the new content is already present and appends it if not."""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_content = f.read()
        if new_content.strip() not in existing_content:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write("\n\n" + new_content)
    else:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)


@csrf_protect
@require_POST
def generate_code(request):
    """Handles the generation of code for a project based on user input and AI response."""
    try:
        # Parse the incoming JSON request body
        user_input = json.loads(request.body)
        project_id = user_input.get('project_id')
        module_name = user_input.get('module_name')
        language = user_input.get('language')
        code_request = user_input.get('code_request')
        user_location = user_input.get('save_path', '').strip()
        save_path = user_input.get("save_path", "")
        
        metadata = user_input.get("metadata", {})
        # New fields from frontend
        project_name = metadata.get("project_name")
        project_type = metadata.get("project_type", "")
        project_description = metadata.get("project_description", "")
        framework = metadata.get("framework", "")
        framework_version = metadata.get("framework_version", "")
        architecture = metadata.get("architecture", "")
        database = metadata.get("database", "")
        testing_framework = metadata.get("testing_framework", "")
        authentication_method = metadata.get("authentication_method", "")
        deployment_target = metadata.get("deployment_target", "")
        ci_cd_integration = metadata.get("ci_cd_integration", "")
        api_documentation = metadata.get("api_documentation", "")
        env_management = metadata.get("env_management", "")
        initial_modules = metadata.get("initial_modules", "")

        # Construct user request with metadata
        user_request = f"""
{code_request}

Additional Project Info:
- Project Name: {project_name}
- Project Type: {project_type}
- Description: {project_description}
- Framework: {framework} {framework_version}
- Architecture: {architecture}
- Database: {database}
- Testing Framework: {testing_framework}
- Authentication: {authentication_method}
- Deployment: {deployment_target}
- CI/CD: {ci_cd_integration}
- API Documentation: {api_documentation}
- Environment Management: {env_management}
- Initial Modules: {initial_modules}
""".strip()

        # Determine base save path considering Desktop/Documents/Downloads shortcut
        system_folders = ["Desktop", "Documents", "Downloads"]

        if user_location in system_folders:
            save_base_path = Path.home() / user_location
        elif user_location:
            # First, check if it might be a path relative to home directory
            if user_location.startswith("~") or user_location.startswith("home/"):
                # Always expand user paths properly
                if user_location.startswith("home/"):
                    # Convert "home/user/Pictures" format to "~/Pictures"
                    parts = user_location.split("/")
                    if len(parts) > 2:  # has at least home/user/something
                        user_location = "~/" + "/".join(parts[2:])
                # Now expand the path
                user_path = Path(user_location).expanduser()
            elif user_location.startswith("/"):
                # Absolute path starting with /
                user_path = Path(user_location)
            else:
                # Standard relative path from current directory
                user_path = Path.cwd() / user_location
            
            # Check if the directory exists before using it
            if not user_path.exists():
                return JsonResponse({
                    "error": f"Directory '{user_path}' does not exist. Please provide a valid path."
                }, status=400)
            
            save_base_path = user_path
        else:
            save_base_path = Path('generated_projects').resolve()
            # Create this default directory if it doesn't exist
            save_base_path.mkdir(exist_ok=True)

        if language and code_request:
            
            # Then modify the generated_name line to provide more information:
            if project_name:
                generated_name = project_name.replace(" ", "_")
                print(f"Using project name: '{project_name}' as folder name: '{generated_name}'")
            else:
                generated_name = f"{language}_project_{ProjectHistory.objects.count() + 1}"
                print(f"No project name provided, using default: '{generated_name}'")
            
            # Ensure the project directory is created directly in the specified path
            project_path = save_base_path / generated_name
            
            # Change here: Ensure the project directory is created directly in the specified path
            os.makedirs(project_path, exist_ok=True)

            # Load security and error handling details
            security_data = load_security_checks()
            security_checks = "\n".join(security_data["security"])
            error_classes = ", ".join(security_data["error_classes"])

            print("Security Checks Applied:")
            
            framework_key = framework.lower().replace(" ", "")
            framework_requirements = framework_requirements_map.get(framework_key, "- No special requirements for this framework.")

            # Format final prompt
            prompt = UNIVERSAL_SYSTEM_PROMPT.format(
                language=language,
                project_name=project_name,
                project_description=project_description,
                project_type=project_type,
                framework=framework,
                framework_version=framework_version,
                architecture=architecture,
                database=database,
                testing_framework=testing_framework,
                authentication_method=authentication_method,
                deployment_target=deployment_target,
                ci_cd_integration=ci_cd_integration,
                api_documentation=api_documentation,
                env_management=env_management,
                initial_modules=initial_modules,
                user_request=user_request,
                security_checks=security_checks,
                error_classes=error_classes,
                framework_requirements=framework_requirements
            )


            # Generate code via OpenAI
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI code generator.\n"
                        "You must respond ONLY with a valid JSON array of files. "
                        "Each file must be a dictionary with 'filename' and 'content' fields. "
                        "Do not add explanations, markdown, or anything else. Only raw JSON."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
            
            ai_response = response.choices[0].message.content
            files = extract_json_array(ai_response)

            if not files or not isinstance(files, list):
                print("Failed to parse JSON response, creating response.txt")
                files = [{"filename": "response.txt", "content": ai_response}]

            # Clean the framework version string if it includes the framework name
            if framework and framework_version:
                
                # If user entered "django 4.2" or similar, strip the name
                if framework_version.lower().startswith(framework.lower()):
                    framework_version = framework_version[len(framework):].strip()

                # Extra safety: just keep digits and dots (e.g., "4.2")
                import re
                match = re.search(r"\d+(\.\d+)*", framework_version)
                if match:
                    framework_version = match.group(0)

            expected_line = f"{framework}=={framework_version}"

            for file in files:
                file_rel_path = file.get("filename")
                if file_rel_path:
                    full_file_path = project_path / file_rel_path
                    os.makedirs(full_file_path.parent, exist_ok=True)
                    with open(full_file_path, 'w', encoding='utf-8') as f:
                        f.write(file.get("content", ""))

            # Record project metadata and files in the database
            ProjectHistory.objects.create(
                language=language,
                user_request=user_request,
                response_files=files,
                project_path=str(project_path),
                project_name=project_name
                 
            )

            return JsonResponse({
                "files": files,
                "project_path": str(project_path),
                "message": f"Project saved at {str(project_path)}"
            })

        else:
            return JsonResponse({
                "error": "Missing required fields. Provide either (language & code_request) or (project_id & module_name)."
            }, status=400)

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@require_GET
def fetch_history(request):
    try:
        project_id = request.GET.get('project_id')
        
        if project_id:
            # If a specific project ID is requested
            try:
                project = ProjectHistory.objects.get(id=int(project_id))
                data = [{
                    "id": project.id,
                    "language": project.language,
                    "user_request": project.user_request,
                    "files": project.response_files,
                    "created_at": project.created_at.strftime("%Y-%m-%d %H:%M"),
                    "project_name":project.project_name
                }]
            except ProjectHistory.DoesNotExist:
                return JsonResponse({"error": "Project not found", "history": []})
        else:
            # Return all history items
            history = ProjectHistory.objects.all().order_by('-created_at')
            data = [{
                "id": p.id,
                "language": p.language,
                "user_request": p.user_request,
                "files": p.response_files,
                "created_at": p.created_at.strftime("%Y-%m-%d "),
                "project_name":p.project_name
            } for p in history]
            
        return JsonResponse({"history": data})
    except Exception as e:
        print(f"ERROR in fetch_history: {str(e)}")
        return JsonResponse({"error": str(e), "history": []})



def save_file_to_project(base_path, filename, content):
    file_path = os.path.join(base_path, filename)
    file_dir = os.path.dirname(file_path)

    # Create directories if they don't exist
    os.makedirs(file_dir, exist_ok=True)

    # Optionally: warn or back up existing file
    if os.path.exists(file_path):
        print(f" Overwriting existing file: {file_path}")

    # Write content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)



@csrf_protect
@require_POST
def continue_project(request):
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        follow_up = data.get('follow_up')

        if not project_id or not follow_up:
            return JsonResponse({"error": "Missing project_id or follow_up"}, status=400)

        # Fetch the project to update
        project = ProjectHistory.objects.get(id=project_id)

       # Get project folder path
        project_base_path = project.project_path  # ← correct field name
        if not project_base_path:
            return JsonResponse({"error": "Project folder path is missing in ProjectHistory"}, status=500)

        # Prepare context from existing files
        context_text = ""
        for file in project.response_files:
            if isinstance(file, dict) and 'filename' in file and 'content' in file:
                context_text += f"\n// File: {file['filename']}\n{file['content']}\n"

        # Prompt to extend project
            
            follow_prompt = f"""
            You are continuing an existing {project.language} project.

            Below are the current files:

            {context_text}

            The user has requested the following task:
            {follow_up}

            DO NOT DELETE or replace existing content in any file.
            If you're modifying an existing file, **include the original content**, and **add new code below** (or modify specific parts if needed, but do not omit unrelated code).
            If you're adding new files, just include them in the list.
            IMPORTANT: DO NOT return empty or placeholder files. Every file MUST contain relevant, working code.
        If a file like views.py or models.py is included, it must contain actual implementations—not stubs or empty definitions.
        For any file you are updating or creating, include the ENTIRE content of that file — not just the new or modified part.

            NEVER return partial file contents. Always assume the system will replace the full file.

            For example, if you're adding a new view, add it **after existing views**, keeping the file whole.

            RETURN FORMAT:
            Return ONLY a valid JSON array like this:
            [
            {{"filename": "api/views.py", "content": "# full content including previous and new code"}}
            ]
            No markdown, no explanation, just the array.
            """

        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a JSON-based code generator."},
                {"role": "user", "content": follow_prompt}
            ]
        )

        ai_response = response.choices[0].message.content
        print("Continuation AI Response Preview:", ai_response[:200])

        # Extract and process the returned JSON files
        new_files = extract_json_array(ai_response)
        new_files = process_file_content(new_files)

        # Update existing file map
        existing_files = project.response_files
        file_map = {file['filename']: file['content'] for file in existing_files if 'filename' in file and 'content' in file}

        # Update or add new files
        for new_file in new_files:
            filename = new_file['filename']
            content = new_file['content']
            file_map[filename] = content  # Overwrite or add

            # Write to actual file system
            save_file_to_project(project_base_path, filename, content)

        # Save back updated files
        updated_files = [{"filename": fname, "content": content} for fname, content in file_map.items()]
        project.response_files = updated_files
        project.save()

        return JsonResponse({"files": new_files})

    except Exception as e:
        print(f" ERROR in continue_project: {str(e)}")
        return JsonResponse({
            "error": str(e),
            "files": [{"filename": "error.txt", "content": f"An error occurred: {str(e)}"}]
        })

def index(request):
    return render(request, "index.html")

@require_GET
def history(request):
    return fetch_history(request)

@csrf_protect
@require_POST
def delete_project(request):
    data = json.loads(request.body)
    project_id = data.get('project_id')
    try:
        project = ProjectHistory.objects.get(id=project_id)
        project.delete()
        return JsonResponse({"success": True})
    except ProjectHistory.DoesNotExist:
        return JsonResponse({"success": False, "error": "Project not found"})

# Define core files for different languages
        core_files = [
    'urls.py', 'views.py', 'models.py', 'settings.py', 'wsgi.py', 'asgi.py',
    'manage.py', 'requirements.txt', 'config.py', 'forms.py', 'middleware.py',
    'admin.py', 'serializers.py', 'tests.py', 'apps.py', '__init__.py',
    'app.js', 'server.js', 'index.js', 'package.json', 'webpack.config.js',
    'babel.config.js', 'tsconfig.json', 'jest.config.js', 'routes.js',
    'main.cpp', 'app.cpp', 'program.cpp', 'CMakeLists.txt', 'Makefile',
    'Main.java', 'App.java', 'Program.java', 'pom.xml', 'gradle.build', 
    'application.properties', 'log4j.xml',
    'index.html', 'main.html', 'style.css', 'script.js', 'manifest.json',
    'service-worker.js',
    'main.go', 'app.go', 'go.mod', 'go.sum',
    'index.php', 'config.php', 'routes.php', 'composer.json',
    'Program.cs', 'Startup.cs', 'appsettings.json', 'project.csproj',

]

@csrf_protect
@require_POST
def generate_module(request):
    try:
        user_input = json.loads(request.body)
        project_id = user_input.get('project_id')
        module_name = user_input.get('module_name')
        description = user_input.get('description')

        if not (project_id and module_name and description):
            return JsonResponse({"error": "Missing required fields: project_id, module_name, description"}, status=400)

        # Fetch the corresponding project from history
        project = ProjectHistory.objects.get(id=project_id)

        # Extract the project name from project_path (Fix for AttributeError)
        project_name = os.path.basename(project.project_path.rstrip('/'))

        # Prepare the module generation prompt
        module_prompt = f"""
        You are working on a {project.language} project named '{project_name}'.
        Generate a module '{module_name}' based on the following description:

        {description}

        Ensure that you include the necessary core files for {project.language}.
        These are the required core files:
        {core_files}

        Return the module as a JSON array of files. 
        Do not use placeholders or 'TODO'.
        
        Instructions:
        - Include ALL required files for the module functionality.
        - If updates are required in existing files like urls.py or settings.py, include updated content.
        - Do not use placeholders or 'TODO'.
        - No markdown, no explanations.
        - Return a valid JSON array of files.
        """

        # Call OpenAI for module generation
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You output ONLY JSON with full code."},
                {"role": "user", "content": module_prompt}
            ]
        )

        ai_response = response.choices[0].message.content
        new_files = extract_json_array(ai_response)

        for file in new_files:
            if "filename" in file and "content" in file:
                file_rel_path = file["filename"]
                content = file["content"]
                full_file_path = os.path.join(project.project_path, file_rel_path)

                # Check if the file is one of the core files across multiple languages
                if any(core_file in os.path.basename(file_rel_path) for core_file in core_files):
                    merge_or_append(full_file_path, content)
                else:
                    os.makedirs(os.path.dirname(full_file_path), exist_ok=True)
                    with open(full_file_path, 'w', encoding='utf-8') as f:
                        f.write(content)

        # **Step 1: Verify Missing Core Files**
        for core_file in core_files:
            core_file_clean = core_file.strip()
            full_file_path = os.path.join(project.project_path, core_file_clean)

            if not os.path.exists(full_file_path):
                missing_files.append(core_file_clean)

        # **Step 2: Retry Generating Missing Files**
        if missing_files:
            print(f"⚠️ Missing core files detected: {missing_files}")

            for missing_file in missing_files:
                regenerate_core_file(project.project_path, missing_file)

        # **Step 3: Final Verification After Regeneration**
        final_missing = verify_missing_files(project.project_path, core_files)
        if final_missing:
            return JsonResponse({"error": f"Some core files are still missing after retry: {final_missing}"}, status=500)

        # Update project history
        project.response_files.extend(new_files)
        project.save()

        return JsonResponse({
            "files": new_files,
            "message": f"Module '{module_name}' generated and updated successfully in project '{project_name}'."
        })

    except ProjectHistory.DoesNotExist:
        return JsonResponse({"error": "Project not found."}, status=404)
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)

# **Helper Functions**
def verify_missing_files(project_path, core_files):
    """Verify if any core files are still missing."""
    still_missing = []
    for core_file in core_files:
        full_file_path = os.path.join(project_path, core_file.strip())
        if not os.path.exists(full_file_path):
            still_missing.append(core_file)
    return still_missing

def regenerate_core_file(project_path, file_name):
    """Attempt to regenerate a missing core file using AI."""
    full_file_path = os.path.join(project_path, file_name)
    
    try:
        # Call AI API to regenerate content (Replace with your actual AI call)
        regenerated_content = f"# Regenerated {file_name} using AI API\n"

        os.makedirs(os.path.dirname(full_file_path), exist_ok=True)
        with open(full_file_path, 'w', encoding='utf-8') as f:
            f.write(regenerated_content)
        
        print(f" {file_name} regenerated successfully.")
    
    except Exception as e:
        print(f" Failed to regenerate {file_name}: {e}")



def generate_module_for_project(module_name, description):
       return [
        {"filename": f"{module_name}.py", "content": f"# Module: {module_name}\n\n\"\"\"{description}\"\"\"\n\nprint('Module {module_name} loaded')\n"}
    ]



