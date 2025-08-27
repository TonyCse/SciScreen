import pandas as pd

# Créer des données de test
data = {
    'Title': [
        'Machine Learning in Healthcare Applications',
        'AI Ethics and Society: A Comprehensive Review',
        'Deep Learning Applications in Medical Imaging',
        'Data Science Trends in 2024',
        'Quantum Computing Advances and Applications',
        'Natural Language Processing for Healthcare',
        'Computer Vision in Autonomous Vehicles',
        'Blockchain Technology in Supply Chain',
        'Cybersecurity in IoT Devices',
        'Robotics in Manufacturing Industry'
    ],
    'Authors': [
        'Smith, J.; Doe, A.; Wilson, K.',
        'Johnson, B.; Brown, M.',
        'Davis, L.; Garcia, R.',
        'Miller, K.; Lee, S.',
        'Taylor, P.; Anderson, C.',
        'Thompson, D.; White, J.',
        'Clark, M.; Lewis, B.',
        'Walker, A.; Hall, E.',
        'Young, P.; King, R.',
        'Wright, S.; Lopez, M.'
    ],
    'Journal': [
        'Nature Medicine',
        'Science Ethics Review',
        'IEEE Transactions on Medical Imaging',
        'Journal of Data Science',
        'Physical Review Quantum',
        'Computational Linguistics',
        'IEEE Computer Vision',
        'Blockchain Research',
        'Cybersecurity Journal',
        'Robotics and Automation'
    ],
    'Year': [2023, 2022, 2024, 2023, 2024, 2023, 2022, 2024, 2023, 2024],
    'Abstract': [
        'This comprehensive study explores the application of machine learning algorithms in healthcare diagnostics, focusing on predictive models for early disease detection.',
        'An in-depth examination of ethical considerations in artificial intelligence deployment across various sectors, including healthcare, finance, and education.',
        'Comprehensive review of deep learning methodologies and their practical applications in medical imaging, including CNN architectures and transfer learning.',
        'Analysis of emerging trends in data science for 2024, including MLOps, AutoML, and the integration of AI in business intelligence platforms.',
        'Recent developments in quantum computing algorithms and their potential applications in cryptography, optimization, and scientific computing.',
        'Investigation of natural language processing techniques for healthcare applications, including clinical text mining and patient data analysis.',
        'Study of computer vision applications in autonomous vehicle navigation, including object detection, lane recognition, and real-time decision making.',
        'Exploration of blockchain technology implementation in supply chain management, focusing on transparency, traceability, and security.',
        'Analysis of cybersecurity challenges in Internet of Things devices, including vulnerability assessment and protection strategies.',
        'Review of robotics applications in modern manufacturing, including automation, quality control, and human-robot collaboration.'
    ]
}

# Créer le DataFrame
df = pd.DataFrame(data)

# Sauvegarder en Excel
df.to_excel('data_test.xlsx', index=False, engine='openpyxl')
print("✅ Fichier data_test.xlsx créé avec 10 articles de test!")

