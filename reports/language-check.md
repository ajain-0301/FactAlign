# Language check results

Model: `qwen/qwen3.8-27b`. Each input contains 15 words. Both README strategies used short output and the original language. Hybrid verification was requested.

11 requests used on this retry; 12 total including the earlier failed attempt. No automatic retries. Final Hinglish factuality verification was skipped when the approved request budget was reached.

## hi

Input: सरकार ने सोमवार को दिल्ली में छात्रों के लिए दस विद्यालय खोलने की घोषणा की।

### standard

दिल्ली सरकार की ओर से सोमवार को दो बड़े सामाजिक कार्यों की घोषणा की गई, जिनमें 10 नए विद्यालय खोलना और जून तक 30,000 भर्तियां करना शामिल है।

Output words: 28. Hybrid verification: contradicted.

### factuality

सरकार ने सोमवार को दिल्ली में छात्रों के लिए दस विद्यालय खोलने की घोषणा की है।

Output words: 16. Hybrid verification: supported.

## en

Input: The government announced ten new schools for students in Delhi on Monday during its meeting.

### standard

Government announced that ten new schools will be established in Delhi for students.

Output words: 13. Hybrid verification: supported.

### factuality

The government announced ten new schools for students in Delhi during its Monday meeting.

Output words: 14. Hybrid verification: supported.

## hinglish

Input: Government ne Monday ko Delhi mein students ke liye das schools kholne ka announcement kiya.

### standard

Government ne Monday ko Delhi mein students ke liye saat schools kholne ka announcement kiya.

Output words: 15. Hybrid verification: contradicted.

### factuality

Government ne Monday ko Delhi mein students ke liye das schools kholne ka announcement kiya.

Output words: 15. Hybrid verification: Not run (request budget reached).

## Assessment

Standard Hindi invented June and 30,000 recruitments. Standard Hinglish changed ten schools (das) to seven (saat). Both were flagged contradicted by hybrid verification. Both English summaries were supported. Hindi factuality was supported; Hinglish factuality exactly copied the source but its hybrid verification was not run. Hindi factuality expanded the 15-word source to 16 words. These tiny inputs are a smoke check, not a benchmark.

The Hindi verifier labels unsupported recruitment information contradicted; that verdict is reported as returned by the code, and absence of a fact alone does not establish a contradiction.
