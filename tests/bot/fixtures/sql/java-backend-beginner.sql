---------------------------
delete from interviews
WHERE id ='b323c6a1-4749-4922-876f-72b6c426b2a6';

INSERT INTO interviews (
    id,
    candidate_id,
    status,
    cv_analysis_id,
    current_question_index,
    plan_metadata,
    adaptive_follow_ups,
    current_parent_question_id,
    current_followup_count,
    started_at,
    completed_at,
    created_at,
    updated_at
) VALUES (
    'b323c6a1-4749-4922-876f-72b6c426b2a6'::uuid,
    '102ea1b3-f664-4617-8f43-fdde557f12b6'::uuid,
    'IDLE',
    '206a91e8-27f4-4bb7-a4f3-ca894e75e88c'::uuid,
    0,
    '{}'::jsonb,
    ARRAY[]::uuid[],
    NULL,
    0,
    '2025-11-23 04:55:38.55251'::timestamp,
    NULL,
    NOW(),
    '2025-11-23 04:55:38.55251'::timestamp
);

------------------------------------------------
DELETE FROM questions
WHERE id IN (
  'f405aaad-3e97-401f-bd5c-d68c62bb1445',
  '453523fb-8ac5-43d9-8aa8-856803fa950d'
);

INSERT INTO questions (
  id,
  text,
  skills,
  version,
  embedding,
  created_at,
  updated_at,
  ideal_answer,
  rationale,
  question_type,
  difficulty
)
VALUES
(
  'f405aaad-3e97-401f-bd5c-d68c62bb1445',
  'Can you describe what Spring Boot is and how it facilitates the development of Spring applications?',
  ARRAY['Spring Boot'],
  1,
  NULL,
  '2025-11-24 09:18:22.761836',
  '2025-11-24 09:18:22.761836',
  'Spring Boot is an extension of the Spring Framework that simplifies the process of building Spring applications by providing a set of conventions and out-of-the-box configurations. It eliminates much of the boilerplate code and configuration that is typically required when setting up a new Spring application, making it easier for developers to start building applications rapidly. With Spring Boot, developers can create stand-alone, production-grade applications that can be run with minimal configuration. One of its standout features is the embedded web server support, allowing developers to run applications as Java applications without needing to deploy them to an external server. Spring Boot also includes a comprehensive set of starter dependencies that simplify dependency management, enabling developers to add necessary libraries with ease. Additionally, it offers features like auto-configuration, which intelligently configures beans based on the libraries on the classpath, and Spring Boot Actuator, which provides production-ready features such as health checks and metrics. For instance, when developing a microservice, Spring Boot can quickly set up a REST API with the necessary configurations, allowing the developer to focus more on business logic rather than infrastructure setup. Overall, Spring Boot enhances productivity and accelerates the development lifecycle.',
  'This question tests the candidate’s understanding of Spring Boot, which is increasingly popular for developing microservices and web applications. Proficiency in Spring Boot indicates a developer''s ability to efficiently build and deploy applications, which is crucial for modern software development.',
  'technical',
  'easy'
),
(
  '453523fb-8ac5-43d9-8aa8-856803fa950d',
  'Can you explain the concept of Java''s garbage collection and how it impacts performance?',
  ARRAY['Java'],
  1,
  NULL,
  '2025-11-24 09:32:14.099725',
  '2025-11-24 09:32:14.099725',
  'Java''s garbage collection (GC) is an automatic memory management process that identifies and discards objects that are no longer in use, freeing up memory resources. Java uses various algorithms for garbage collection, including the Mark and Sweep, which marks reachable objects and sweeps away the unmarked ones, and the Generational Garbage Collection, which categorizes objects by their lifespan. This impacts performance greatly; while GC helps prevent memory leaks, it can also introduce latency during the collection process, especially if it occurs at an inopportune time, such as during peak application load. For instance, if an application allocates and deallocates many short-lived objects, frequent GC cycles may lead to application pauses. To mitigate this, developers can optimize their code by minimizing unnecessary object creation and choosing appropriate GC settings based on application needs. A practical example is using the G1 Garbage Collector for applications needing predictable pause times as it divides the heap into regions and can focus on collecting the most garbage while maintaining application responsiveness.',
  'This question assesses the candidate''s understanding of Java''s memory management and performance implications. It tests their knowledge of key concepts related to garbage collection, which is crucial for efficient Java application development, particularly in backend systems where resource optimization is critical.',
  'technical',
  'medium'
);

------------------------------------------------

delete from interview_questions
WHERE interview_id ='b323c6a1-4749-4922-876f-72b6c426b2a6';

INSERT INTO interview_questions (
    id,
    interview_id,
    question_id,
    sequence_order,
    asked_at,
    skipped,
    skip_reason,
    created_at
) VALUES
(
    '7809a338-2606-442f-ad5a-b50f0bd2d710'::uuid,
    'b323c6a1-4749-4922-876f-72b6c426b2a6'::uuid,
    '453523fb-8ac5-43d9-8aa8-856803fa950d'::uuid,
    0,
    NULL,
    false,
    NULL,
    NOW()
),
(
    '3c99a977-e84a-43d0-a561-e201d6d0a5b0'::uuid,
    'b323c6a1-4749-4922-876f-72b6c426b2a6'::uuid,
    'f405aaad-3e97-401f-bd5c-d68c62bb1445'::uuid,
    1,
    NULL,
    false,
    NULL,
    NOW()
);

-------------------------------------

delete from checkpoints
WHERE thread_id LIKE '%b323c6a1-4749-4922-876f-72b6c426b2a6%';