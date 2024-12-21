import React from 'react';
import Header from './components/Header';
import ItemList from './components/ItemList';
import './styles/App.css';

const App = () => {
    return (
        <div className="App">
            <Header />
            <main>
                <ItemList />
            </main>
        </div>
    );
};

export default App;