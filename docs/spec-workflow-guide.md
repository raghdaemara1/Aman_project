# Spec-Driven Development with Claude Code

Welcome to Spec-Driven Development (SDD)! The goal of Spec Kit is to stop jumping straight into writing code and instead focus on **design, planning, and architecture** first. This makes AI coding agents (like Claude) significantly more reliable.

To answer your question: **Yes, you should absolutely run Claude and discuss the business requirements first.** In fact, that is explicitly step 2 of the workflow.

Here is the step-by-step workflow on how to use Spec Kit with Claude Code.

---

### Step 1: Set the Rules (The Constitution)
Before writing any code or even requirements, you define your project's non-negotiable rules.
- **Action:** Open `.specify/constitution.md` and define your tech stack, architectural rules, and coding standards. 
- **Example:** "We use Next.js with App Router. Always use TailwindCSS for styling. Do not use classes for components, only functional React components."
- **Claude Command:** You can run `claude` and type `/speckit.constitution` to have Claude review or help you define these rules based on a brief prompt.

### Step 2: Discuss Business Requirements (The Specification)
This is exactly what you asked about! You don't write code yet; you talk to Claude about what you want to build.
- **Action:** Run `claude` in your terminal.
- **Command:** Type `/speckit.specify` and explain your idea. 
- **What happens:** Claude will ask you clarifying questions about the business requirements, features, and user experience. It will then document everything in `.specify/spec.md`. This becomes the single source of truth for *what* you are building.

### Step 3: Architecture & Planning
Once the business requirements in `spec.md` look good, you ask Claude how to build it technically.
- **Action:** In Claude Code, type `/speckit.plan`.
- **What happens:** Claude reads your `constitution.md` and `spec.md`, and creates a detailed technical implementation plan in `.specify/plan.md`. This covers database schemas, component structures, and API routes. You can review this plan and ask Claude to adjust it if needed.

### Step 4: Breaking it into Tasks
AI coding works best in small, manageable chunks. 
- **Action:** In Claude Code, type `/speckit.tasks`.
- **What happens:** Claude takes the `plan.md` and breaks it down into step-by-step actionable items inside `.specify/tasks.md`. 

### Step 5: Implementation (Finally, Code!)
Now that everything is perfectly planned and broken down, Claude can write the code.
- **Action:** In Claude Code, type `/speckit.implement`.
- **What happens:** Claude will look at the first unchecked task in `.specify/tasks.md`, write the code for it, test it, and then check it off. You repeat this command or let Claude proceed until all tasks are complete.

---

### Summary of Commands to Use Inside `claude`
1. `/speckit.constitution` - Set up architecture and rules.
2. `/speckit.specify` - Discuss business requirements and write the spec.
3. `/speckit.plan` - Generate the technical design.
4. `/speckit.tasks` - Break the design into steps.
5. `/speckit.implement` - Write the code step-by-step.

By following this workflow, Claude acts as your Architect *first*, your Technical Lead *second*, and your Junior Developer *last*.
