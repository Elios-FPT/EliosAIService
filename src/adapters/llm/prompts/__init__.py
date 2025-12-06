"""Prompt templates for LangChain adapter.

All LLM prompts are centralized here as Python constants (fallback)
and can be overridden by database-stored prompts
"""

from langchain_core.prompts import ChatPromptTemplate

# System prompts
SYSTEM_INTERVIEWER = """You are an expert technical interviewer evaluating candidates for software engineering positions.
Your role is to ask relevant, challenging questions and provide constructive feedback."""

SYSTEM_EVALUATOR = """You are an expert technical interviewer evaluating candidate answers.
Provide fair, constructive feedback focusing on technical accuracy, depth, and communication."""

SYSTEM_CV_ANALYZER = """You are an expert HR professional and technical recruiter analyzing candidate CVs.
Extract relevant information accurately and professionally."""


# 1. Generate Question
GENERATE_QUESTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_INTERVIEWER),
    ("human", """Generate a {difficulty} difficulty interview question to test: {skill}

Context:
- Candidate's background: {cv_summary}
- Previous topics covered: {covered_topics}
- Interview stage: {stage}

{exemplar_section}

**IMPORTANT CONSTRAINTS**:
The question MUST be verbal/discussion-based. DO NOT generate questions that require:
- Writing code ("write a function", "implement", "create a class", "code a solution")
- Drawing diagrams ("draw", "sketch", "diagram", "visualize", "map out")
- Whiteboard exercises ("design on whiteboard", "show on board", "illustrate")
- Visual outputs ("create a flowchart", "design a schema visually")

Focus on conceptual understanding, best practices, trade-offs, and problem-solving approaches that can be explained verbally.

Return the question in JSON format:
{{
    "question_text": "your question here",
    "reasoning": "brief explanation of relevance (optional)"
}}""")
])


# 2. Evaluate Answer
EVALUATE_ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_EVALUATOR),
    ("human", """Evaluate this interview answer.

Question: {question_text}
Question Type: {question_type}
Difficulty: {difficulty}
Expected Skills: {skills}

Candidate's Answer:
{answer_text}

{ideal_answer_section}

{followup_context_section}

Evaluation Criteria:
1. Technical Accuracy (0-40 points)
2. Depth of Understanding (0-30 points)
3. Clarity of Communication (0-20 points)
4. Practical Application (0-10 points)
{semantic_similarity_section}

Return evaluation in JSON format:
{{
    "score": 85.5,
    "feedback": "detailed feedback here",
    "strengths": ["point 1", "point 2"],
    "weaknesses": ["point 1", "point 2"],
    "missing_concepts": ["concept 1", "concept 2"]{semantic_similarity_key}
}}""")
])


# 3. Generate Ideal Answer
IDEAL_ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_INTERVIEWER),
    ("human", """Generate an ideal answer for this interview question.

Question: {question_text}

Context:
- Candidate background: {cv_summary}
- Target skill level: {skill_level}

Requirements:
- Length: 150-300 words
- Include: key concepts, practical examples, best practices
- Avoid: overly technical jargon without explanation

Return in JSON format:
{{
    "answer_text": "ideal answer here (150-300 words)"
}}""")
])


# 4. Generate Rationale
RATIONALE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_INTERVIEWER),
    ("human", """Explain why this is an ideal answer.

Question: {question_text}

Ideal Answer:
{ideal_answer}

Provide a brief rationale (50-100 words) explaining what makes this answer ideal.
Focus on: key concepts covered, depth, clarity, practical value.

Return in JSON format:
{{
    "rationale_text": "explanation here (50-100 words)"
}}""")
])


# 5. Detect Concept Gaps
DETECT_GAPS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_EVALUATOR),
    ("human", """Analyze gaps in the candidate's answer.

Question: {question_text}

Ideal Answer:
{ideal_answer}

Candidate's Answer:
{answer_text}

Potential Missing Keywords (from keyword analysis):
{keyword_gaps}

Task:
1. Identify key concepts missing from candidate's answer
2. Confirm which keywords represent actual conceptual gaps
3. Assess severity of gaps

Return in JSON format:
{{
    "concepts": ["missing concept 1", "missing concept 2"],
    "keywords": ["confirmed keyword 1", "confirmed keyword 2"],
    "confirmed": true,
    "severity": "moderate"
}}

Severity levels:
- "minor": Answer covers main points, missing only details
- "moderate": Missing important concepts but core understanding present
- "major": Fundamental concepts missing or misunderstood""")
])


# 6. Generate Follow-up Question
FOLLOWUP_QUESTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_INTERVIEWER),
    ("human", """Generate a targeted follow-up question.

Original Question: {parent_question}

Latest Answer:
{answer_text}

Current Missing Concepts: {missing_concepts}
Gap Severity: {severity}
{cumulative_context}
{previous_context}

Generate focused follow-up question (#{order}) addressing the most critical missing concepts.
The question should:
- Be specific and concise
- Prioritize concepts: {priority_concepts}
- Avoid repeating previous follow-up questions
- Be progressively more targeted (this is follow-up #{order} of max 3)

IMPORTANT: Return ONLY valid JSON in this exact format (no additional text):
{{
    "question_text": "follow-up question here"
}}""")
])


# 7. Generate Feedback Report
FEEDBACK_REPORT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_EVALUATOR),
    ("human", """Generate a comprehensive interview feedback report.

Interview ID: {interview_id}
Total Questions: {total_questions}

Questions and Evaluations:
{questions_and_answers}

Generate a professional feedback report including:
1. Overall Performance Summary
2. Key Strengths (3-5 points)
3. Areas for Improvement (3-5 points)
4. Specific Recommendations
5. Next Steps

Format as a well-structured report (300-500 words).

Return in JSON format:
{{
    "report_text": "complete formatted report here",
    "overall_score": 75.5
}}""")
])


# 8. Summarize CV
SUMMARIZE_CV_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_CV_ANALYZER),
    ("human", """Summarize this CV concisely.

CV Text:
{cv_text}

Create a professional summary (100-200 words) highlighting:
- Years of experience (estimate if not explicit)
- Key technical skills
- Notable projects or achievements
- Education background

Return in JSON format:
{{
    "summary_text": "summary here (100-200 words)",
    "years_experience": 5
}}""")
])


# 9. Extract Skills
EXTRACT_SKILLS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_CV_ANALYZER),
    ("human", """Extract technical skills from this text.

Text:
{text}

Identify:
- Programming languages
- Frameworks and libraries
- Databases and tools
- Methodologies and practices

For each skill, provide:
- name: skill name
- category: type of skill (e.g., "programming", "framework", "database")
- proficiency: level if mentioned (e.g., "beginner", "intermediate", "expert")

Return in JSON format:
{{
    "skills": [
        {{"name": "Python", "category": "programming", "proficiency": "expert"}},
        {{"name": "FastAPI", "category": "framework", "proficiency": "intermediate"}}
    ]
}}""")
])


# 10. Generate Interview Recommendations
RECOMMENDATIONS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_EVALUATOR),
    ("human", """Generate personalized interview recommendations.

Interview Context:
- Interview ID: {interview_id}
- Total Answers: {total_answers}
- Gap Progression: {gap_progression}
- Evaluations: {evaluations}

Provide:
1. Top 3-5 strengths demonstrated
2. Top 3-5 weaknesses to address
3. Specific study topics (be concrete)
4. Interview technique tips (voice, pacing, structure)

Return in JSON format:
{{
    "strengths": ["strength 1", "strength 2", ...],
    "weaknesses": ["weakness 1", "weakness 2", ...],
    "study_topics": ["topic 1", "topic 2", ...],
    "technique_tips": ["tip 1", "tip 2", ...]
}}""")
])


# Batch prompts (aggregated format for LangChain adapter + DB template)
BATCH_QUESTIONS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_INTERVIEWER),
    ("human", """Generate {question_count} interview questions based on the specifications below.

Context:
- Candidate's background: {summary}
- Key Skills: {skills}
- Experience: {experience} years

Specifications:
{questions_section}

**IMPORTANT CONSTRAINTS**:
The questions MUST be verbal/discussion-based. DO NOT generate questions that require:
- Writing code ("write a function", "implement", "create a class", "code a solution")
- Drawing diagrams ("draw", "sketch", "diagram", "visualize", "map out")
- Whiteboard exercises ("design on whiteboard", "show on board", "illustrate")
- Visual outputs ("create a flowchart", "design a schema visually")

Focus on conceptual understanding, best practices, trade-offs, and problem-solving approaches that can be explained verbally.

Return ONLY valid JSON in this exact format:
{
    "questions": ["question 1 text", "question 2 text", "... up to question_count ..."]
}
""")
])
BATCH_IDEAL_ANSWERS_PROMPT = IDEAL_ANSWER_PROMPT
BATCH_RATIONALES_PROMPT = RATIONALE_PROMPT

# 11. Generate Question with Answer and Rationale (Unified)
GENERATE_QUESTION_WITH_ANSWER_AND_RATIONALE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_INTERVIEWER),
    ("human", """Generate a complete interview question set: question, ideal answer, and rationale.

Generate a {difficulty} difficulty interview question to test: {skill}

Context:
- Candidate's background: {cv_summary}
- Previous topics covered: {covered_topics}
- Interview stage: {stage}

{exemplar_section}

**IMPORTANT CONSTRAINTS**:
The question MUST be verbal/discussion-based. DO NOT generate questions that require:
- Writing code ("write a function", "implement", "create a class", "code a solution")
- Drawing diagrams ("draw", "sketch", "diagram", "visualize", "map out")
- Whiteboard exercises ("design on whiteboard", "show on board", "illustrate")
- Visual outputs ("create a flowchart", "design a schema visually")

Focus on conceptual understanding, best practices, trade-offs, and problem-solving approaches that can be explained verbally.

Requirements:
1. Question: Clear, relevant, and appropriate for the skill and difficulty level
2. Ideal Answer: 150-300 words demonstrating expert-level understanding with key concepts, practical examples, and best practices
3. Rationale: 50-100 words explaining why this answer is ideal, focusing on key concepts covered, depth, clarity, and practical value

Return in JSON format:
{{
    "question_text": "your question here",
    "ideal_answer": "ideal answer here (150-300 words)",
    "rationale": "explanation of why this answer is ideal (50-100 words)"
}}""")
])


# 12. Comprehensive Answer Analysis (Phase 2: Unified LLM Prompt)
COMPREHENSIVE_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert technical interviewer. Analyze candidate answers comprehensively using step-by-step reasoning.

CRITICAL: Evaluate each answer independently based on its actual quality. Do not anchor to example scores or default values. Use the full scoring range for each dimension based on merit.

Provide analysis in THREE PARTS:
1. EVALUATION: Multi-dimensional scoring (technical accuracy, depth, clarity, practical application)
2. GAP DETECTION: Identify missing concepts with severity ratings
3. FOLLOW-UP DECISION: Suggest follow-up question if major gaps exist and attempt < 3

Use chain-of-thought reasoning for quality multi-task analysis."""),
    ("human", """Analyze this answer comprehensively.

QUESTION: {question_text}
IDEAL ANSWER: {ideal_answer}
CANDIDATE'S ANSWER: {answer_text}

CONTEXT:
- Attempt number: {attempt_number}
- Previous scores: {previous_scores}
- Cumulative gaps: {cumulative_gaps}

**PART 1: EVALUATION**
Evaluate answer on 4 dimensions:
- Technical accuracy (0-40 points): Correctness of concepts and implementation details
- Depth of understanding (0-30 points): Level of detail and comprehension shown
- Clarity of communication (0-20 points): Structure, coherence, and articulation
- Practical application (0-10 points): Real-world relevance and examples

For each dimension, provide score + reasoning.
Calculate total score (0-100).

**PART 2: GAP DETECTION**
Compare answer to ideal answer. Identify missing concepts or incomplete explanations.
For each gap, rate severity:
- "minor": Nice-to-know details, doesn't affect core understanding
- "moderate": Important concepts that should be mentioned
- "major": Critical concepts essential for complete answer

**PART 3: FOLLOW-UP DECISION**
Conditions for follow-up:
- If major gaps exist AND attempt < 3: Suggest ONE follow-up question to probe deeper
- If no major gaps OR attempt == 3: Return null for follow_up

Return valid JSON with all three parts.

CRITICAL: Evaluate each answer independently. Base scores on actual answer quality, not on examples. Use the full scoring range (0 to max) for each dimension based on merit.

JSON structure:
{{
    "evaluation": {{
        "dimensions": [
            {{"dimension_name": "technical_accuracy", "score": <number 0-40>, "reasoning": "evaluate correctness of concepts and implementation"}},
            {{"dimension_name": "depth_of_understanding", "score": <number 0-30>, "reasoning": "evaluate level of detail and comprehension"}},
            {{"dimension_name": "clarity_of_communication", "score": <number 0-20>, "reasoning": "evaluate structure, coherence, and articulation"}},
            {{"dimension_name": "practical_application", "score": <number 0-10>, "reasoning": "evaluate real-world relevance and examples"}}
        ],
        "total_score": <number 0-100, sum of dimension scores>,
        "strengths": ["list specific strengths found in answer"],
        "weaknesses": ["list specific weaknesses found in answer"],
        "improvement_suggestions": ["list actionable improvement suggestions"],
        "reasoning": "overall evaluation summary"
    }},
    "gaps": [
        {{"concept": "name of missing concept", "severity": "minor|moderate|major", "explanation": "explain why this is a gap"}}
    ],
    "follow_up": {{
        "question_text": "<follow-up question string> or null",
        "reason": "<reason for follow-up> or null",
        "target_gaps": ["list gap concepts this follow-up addresses"]
    }},
    "confidence": <number 0.0-1.0>
}}""")
])


# Prompt registry for easy access
PROMPT_REGISTRY = {
    "generate_question": GENERATE_QUESTION_PROMPT,
    "evaluate_answer": EVALUATE_ANSWER_PROMPT,
    "generate_ideal_answer": IDEAL_ANSWER_PROMPT,
    "generate_rationale": RATIONALE_PROMPT,
    "detect_concept_gaps": DETECT_GAPS_PROMPT,
    "generate_followup_question": FOLLOWUP_QUESTION_PROMPT,
    "generate_feedback_report": FEEDBACK_REPORT_PROMPT,
    "summarize_cv": SUMMARIZE_CV_PROMPT,
    "extract_skills_from_text": EXTRACT_SKILLS_PROMPT,
    "generate_interview_recommendations": RECOMMENDATIONS_PROMPT,
    "generate_questions_batch": BATCH_QUESTIONS_PROMPT,
    "generate_ideal_answers_batch": BATCH_IDEAL_ANSWERS_PROMPT,
    "generate_rationales_batch": BATCH_RATIONALES_PROMPT,
    "generate_questions_with_answers_and_rationales_batch": GENERATE_QUESTION_WITH_ANSWER_AND_RATIONALE_PROMPT,
    "comprehensive_answer_analysis": COMPREHENSIVE_ANALYSIS_PROMPT,  # Phase 2: Unified prompt
}
