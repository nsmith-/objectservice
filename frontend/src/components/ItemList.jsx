import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from 'react-oidc-context';

const ItemList = () => {
    const [items, setItems] = useState([]);
    const [newItem, setNewItem] = useState({ type: '', data: '' });

    const apiBaseUrl = process.env.REACT_APP_API_BASE_URL;
    const auth = useAuth();

    useEffect(() => {
        const fetchItems = async () => {
            if (auth.isAuthenticated) {
                try {
                    const response = await axios.get(`${apiBaseUrl}/items/`, {
                        headers: {
                            Authorization: `Bearer ${auth.user.access_token}`,
                        },
                    });
                    setItems(response.data);
                } catch (error) {
                    console.error('Error fetching items:', error);
                }
            }
        };

        fetchItems();
    }, [apiBaseUrl, auth.isAuthenticated, auth.user]);

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setNewItem({ ...newItem, [name]: value });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (auth.isAuthenticated) {
            try {
                const response = await axios.post(`${apiBaseUrl}/items/`, newItem, {
                    headers: {
                        Authorization: `Bearer ${auth.user.access_token}`,
                    },
                });
                setItems([...items, response.data]);
                setNewItem({ type: '', data: '' });
            } catch (error) {
                console.error('Error adding item:', error);
            }
        }
    };

    const handleDelete = async (id) => {
        if (auth.isAuthenticated) {
            try {
                await axios.delete(`${apiBaseUrl}/items/${id}`, {
                    headers: {
                        Authorization: `Bearer ${auth.user.access_token}`,
                    },
                });
                setItems(items.filter(item => item.id !== id));
            } catch (error) {
                console.error('Error deleting item:', error);
            }
        }
    };

    if (!auth.isAuthenticated) {
        return <div>Please log in to view items.</div>;
    }

    return (
        <div>
            <h1>Items</h1>
            <ul>
                {items.map(item => (
                    <li key={item.id}>
                        <h2>{item.type}</h2>
                        <p>Owner: {item.owner.name}</p>
                        <p>Created on: {new Date(item.create_date).toLocaleString()}</p>
                        <pre>{JSON.stringify(item.data, null, 2)}</pre>
                        <button onClick={() => handleDelete(item.id)}>Delete</button>
                    </li>
                ))}
            </ul>
            <h2>Add New Item</h2>
            <form onSubmit={handleSubmit}>
                <div>
                    <label>Type:</label>
                    <input
                        type="text"
                        name="type"
                        value={newItem.type}
                        onChange={handleInputChange}
                        required
                    />
                </div>
                <div>
                    <label>Data:</label>
                    <textarea
                        name="data"
                        value={newItem.data}
                        onChange={handleInputChange}
                        required
                    />
                </div>
                <button type="submit">Add Item</button>
            </form>
        </div>
    );
};

export default ItemList;